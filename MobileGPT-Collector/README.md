# MobileGPT-Collector

KeyUI 기반 자동 모바일 앱 화면 데이터 수집기.

Android 앱을 자동 탐색하면서 화면을 수집하고, KeyUI 매칭으로 유사 화면을 동일 번들로 그룹핑합니다.

## 개요

MobileGPT-Collector는 **Android 클라이언트 앱**과 **Python 서버** 두 컴포넌트로 구성됩니다:

1. **app_collector** (Android): 접근성 서비스로 화면 XML/스크린샷을 캡처하여 서버에 전송하고, 서버의 액션 명령을 실행
2. **Server** (Python): LangGraph 기반 GREEDY 탐색으로 앱을 자동 탐색하며, KeyUI 매칭으로 유사 화면을 분류/저장

### 처리 파이프라인

1. **화면 수신**: Android 클라이언트(app_collector)로부터 XML + 스크린샷 수신
2. **Subtask 추출**: LLM으로 화면에서 수행 가능한 서브태스크 추출
3. **Safety 필터링**: 위험한 서브태스크 (결제, 삭제, 로그인 등) 자동 차단
4. **KeyUI 선택**: 각 서브태스크를 대표하는 UI 요소 (KeyUI) 선택
5. **페이지 매칭**: KeyUI 속성 비교로 기존 번들과 유사도 판정 (EQSET/SUPERSET/SUBSET/VARIANT/NEW)
6. **데이터 저장**: MobileGPT-Collector 포맷 + MobileGPT-V2 메모리 포맷 동시 저장
7. **GREEDY 탐색**: BFS 기반 최단 경로로 미탐색 서브태스크를 순차 탐색
8. **메모리 파이프라인**: 수집 데이터를 MobileGPT-V2 Task mode에서 바로 사용 가능한 형식으로 저장

### 처리 파이프라인 상세

#### 1. LangGraph State Machine

3개 노드로 구성된 LangGraph 상태 기계가 탐색 루프를 제어합니다:

```
START → supervisor ─┬─→ discover ────→ supervisor (루프)
                    ├─→ explore_action → supervisor (루프)
                    └─→ finish ──────→ END
```

**supervisor 라우팅 조건** (우선순위 순):

| 우선순위 | 조건 | 다음 노드 |
|---------|------|----------|
| 1 | `action`이 이미 설정됨 | `finish` → END |
| 2 | `status == "exploration_complete"` | `finish` → END |
| 3 | `status == "error"` | `finish` → END |
| 4 | `is_new_screen == True` | `discover` |
| 5 | (기본값) | `explore_action` |

`discover`와 `explore_action`은 항상 `supervisor`로 복귀하며, supervisor가 중앙 라우팅 허브 역할을 합니다.

#### 2. XML 전처리

Android UI Automator 원본 XML을 4가지 포맷으로 변환합니다:

```
raw_xml (Android XML)
  ↓ reformat_xml() — class 기반 태그 변환 + simplify_structure() + 빈 bounds 제거
  = parsed_xml

parsed_xml
  ↓ hierarchy_parse() — bounds/important/index/text 제거 + scroll 중복 제거
  = hierarchy_xml

parsed_xml
  ↓ create_encoded_xml() — bounds/important/class 제거 (index 유지)
  = encoded_xml

encoded_xml
  ↓ create_pretty_xml() — 들여쓰기 포맷
  = pretty_xml
```

**태그 변환 규칙:**

| Android class | HTML 태그 | 조건 |
|--------------|-----------|------|
| EditText | `<input>` | - |
| checkable 요소 | `<checker>` | checked 속성 추가 |
| clickable 요소 | `<button>` | - |
| Layout 계열 | `<div>` | FrameLayout, LinearLayout 등 |
| ImageView | `<img>` | - |
| TextView | `<p>` | clickable이 아닌 경우 |
| scrollable 요소 | `<scroll>` | - |

**포맷별 용도:**

| 포맷 | 용도 |
|------|------|
| Parsed XML | KeyUI 매칭 (bounds/index 포함), 페이지 저장 |
| Hierarchy XML | 구조 기반 페이지 유사도 (OpenAI embedding) |
| Encoded XML | LLM 입력 (subtask 추출, KeyUI 선택, 요약) |
| Pretty XML | 사람이 읽기 위한 디버깅용 |

#### 3. Subtask 추출 (LLM)

`SubtaskExtractor`가 encoded XML에서 수행 가능한 서브태스크를 추출합니다.

**추출 규칙:**
- 인터랙터블 요소 식별: `<button>`, `<checker>`, `<input>`, `<scroll>`
- 관련 액션을 고수준으로 병합 (예: `input_name` + `input_email` → `fill_in_info`)
- **일반적 이름** 사용 (화면 특정 내용 배제: `call_contact` ○, `call_Bob` ✕)
- 파라미터는 질문 형태로 정의 (예: `{"contact_name": "Who do you want to call?"}`)

**출력 포맷:**
```json
{"subtasks": [
  {"name": "search", "description": "Search for items", "parameters": {"query": "What to search for?"}}
]}
```

실패 시 최대 2회 재시도하며, 응답 파싱은 다양한 JSON 키 (`subtasks`, `result`, `items`, `data`, `actions`)를 폴백으로 탐색합니다.

#### 4. Safety 필터링

`SafetyFilter`가 위험한 서브태스크를 자동 차단합니다. 상세 카테고리와 키워드는 [Safety 필터](#safety-필터) 섹션을 참조하세요.

매칭 방식:
1. subtask name을 `_`로 분리한 토큰이 키워드와 정확히 일치
2. description에서 word boundary regex (`\b keyword \b`) 매칭

반환: `(safe_subtasks, unsafe_subtasks)` 튜플

#### 5. KeyUI 선택 (LLM)

`KeyUISelector`가 각 서브태스크를 대표하는 UI 요소를 선택합니다.

**4가지 선택 기준:**

| 기준 | 설명 |
|------|------|
| Functional Relevance | subtask를 직접 트리거하거나 활성화하는 UI |
| Uniqueness | 해당 subtask에 고유한 UI (다른 subtask와 구별) |
| Stability | 유사 화면에서 일관되게 나타나는 UI |
| Identifiability | 명확한 속성 보유 (id, description, text) |

**선호/회피 UI 속성:**
- **선호**: unique id, 명확한 text/description, `<button>/<input>/<checker>/<scroll>` 태그
- **회피**: 모든 속성이 `NONE`, 동적 text, 비인터랙터블 요소

출력: `{subtask_name: [UIAttributes]}` — `UIAttributes`는 self/parent/children 3계층 속성을 포함하며, children은 최대 depth 3까지 탐색합니다.

#### 6. 페이지 매칭 (KeyUI 기반)

`PageMatcher`가 현재 화면의 KeyUI 속성을 기존 번들의 KeyUI와 비교하여 매칭 타입을 판정합니다.

**UIAttributes 비교 방식:**
- self/parent/children 각 계층의 속성(tag, id, class, description)을 **exact match**로 비교
- 값이 `NONE`인 속성은 비교에서 제외
- children은 depth + rank 기반 위치 매칭 (최대 depth 3)

**match_ratio 계산:**
```
match_ratio = len(supported_subtasks) / len(total_subtasks)
```

**5가지 매칭 타입 판정:**

| 매칭 타입 | 조건 | 동작 |
|-----------|------|------|
| EQSET | `remaining == 0 && match_ratio == 1.0` | 기존 번들에 추가 |
| SUBSET | `remaining == 0 && match_ratio > 0` | 기존 번들에 추가 |
| SUPERSET | `remaining > 0 && match_ratio >= threshold` | 기존 번들 확장 |
| VARIANT | KeyUI 불일치, Jaccard(subtask names) ≥ subtask_threshold, XML diff 존재 | 같은 번들에 다른 페이지로 추가 |
| NEW | 위 조건 모두 미달 | 새 번들 생성 |

**2단계 매칭 프로세스:**
1. KeyUI 기반 매칭 → 우선순위: EQSET > SUPERSET > SUBSET
2. 폴백: Subtask 이름 Jaccard 유사도 ≥ `subtask_threshold` + encoded XML diff 존재 → VARIANT

#### 7. SUPERSET 확장 (Approach B)

SUPERSET 매칭 시 기존 번들에 새로운 subtask를 추가하는 확장 프로세스입니다.

**Approach B 방식:**
- 전체 encoded XML + 기존 subtask exclusion list를 LLM에 전달
- LLM이 화면 전체 맥락을 보고 exclusion list에 없는 새 subtask를 자유롭게 추출
- remaining UI index를 제한 조건으로 사용하지 않음

**확장 흐름:**
```
SUPERSET 판정
  ↓
expand_prompt: 전체 encoded_xml + excluded_subtask_names → LLM
  ↓
새 Subtask 목록 추출
  ↓
KeyUISelector: 새 subtask별 KeyUI 선택
  ↓
BundleManager.expand_bundle(): 번들에 새 subtask + KeyUI 추가 (중복 제거)
  ↓
PageRegistry 업데이트
```

**참고:** KeyUI 매칭에서 unsupported인 subtask (기존 KeyUI가 현재 화면에 없는 경우)는 해당 페이지에 없는 것으로 간주하며 복구하지 않습니다.

#### 8. 데이터 저장 (Dual Format)

수집 데이터를 두 가지 포맷으로 동시 저장합니다:

**Collector Format** (`data/{app}/`):
- `page_registry.json`: 전체 페이지 지식 (subtask, keyui, encoded_xml)
- `bundle_map.json`: 번들 메타데이터 (subtask, pages, keyuis)
- `{bundle}/{page}/`: 6개 XML 파일 + 스크린샷 + subtask.json + keyui.json

**MobileGPT-V2 Memory Format** (`memory/{app}/`):
- `pages.csv`: 글로벌 페이지 인덱스 (index, subtasks, trigger_uis, summary)
- `hierarchy.csv`: hierarchy XML + OpenAI embedding (코사인 유사도 검색용)
- `subtask_graph.json`: 페이지 간 전이 그래프 (nodes, edges)
- `pages/{index}/`: available_subtasks.csv, subtasks.csv, actions.csv, screen/ 디렉토리

MobileGPT-V2 Memory Format은 Task mode에서 바로 사용 가능한 형식으로, embedding 기반 페이지 검색(`threshold=0.95`)을 지원합니다.

#### 9. GREEDY 탐색 알고리즘

`explore_action_node`가 5단계 우선순위로 다음 액션을 결정합니다:

**Priority 1 — 기존 navigation_plan 실행:**
이전에 계획된 navigation_plan이 있으면 그 첫 번째 step을 실행합니다. forward(click) 또는 back 액션.

**Priority 2 — 현재 페이지의 미탐색 subtask 탐색:**
현재 페이지에 미탐색 subtask가 있으면 첫 번째 것을 선택하여 click 액션을 생성합니다. UI index가 유효하지 않으면 UIAttributes 재매칭으로 폴백합니다.

**Priority 3 — BFS로 가장 가까운 미탐색 페이지 탐색:**
`subtask_graph`와 `back_edges`를 사용해 BFS를 수행하여 미탐색 subtask가 있는 가장 가까운 페이지까지의 navigation_plan(forward/back 시퀀스)을 생성합니다.

**Priority 4 — back 이동:**
BFS에서도 경로를 찾지 못하면 traversal_path를 따라 back으로 복귀합니다.

**Priority 5 — 탐색 완료:**
루트에서 더 이상 탐색할 것이 없으면 `exploration_complete` 상태로 전환하여 종료합니다.

각 click 액션 실행 후 `HistoryAgent`가 시각적 단서 기반 가이드라인을 생성하고, `ExploreMemoryAdapter`가 subtasks.csv와 actions.csv를 업데이트합니다.

#### 10. LLM Agent 역할

| Agent | 입력 | 출력 | 용도 |
|-------|------|------|------|
| SubtaskExtractor | encoded_xml | `list[Subtask]` | 화면에서 수행 가능한 서브태스크 추출 |
| KeyUISelector | subtask + parsed_xml | `{name: [UIAttributes]}` | 서브태스크별 대표 UI 선택 |
| SummaryAgent | encoded_xml + subtasks (+ screenshot) | 자연어 요약 (≤100단어) | 페이지 설명 생성 |
| HistoryAgent | action + screen_xml | 가이드라인 문장 | 시각적 단서 기반 액션 설명 |

모든 LLM Agent는 `LLMClient`를 공유하며, 설정 가능한 모델(`--model`, 기본 gpt-5.2)과 추론 강도(`--reasoning-effort`, 기본 medium)를 사용합니다.

---

## 아키텍처

```
┌─────────────────────────────────┐
│  app_collector (Android)        │
│  ├── CollectorAccessibilityService  │
│  │    ├── XML 계층 캡처              │
│  │    ├── 스크린샷 캡처              │
│  │    └── 액션 실행 (click/back/...) │
│  ├── CollectorClient (TCP)      │
│  └── FloatingButton UI          │
│       ├── Start / Capture / Finish  │
└──────────────┬──────────────────┘
               │  TCP (A/S/X/F)
               ▼
┌─────────────────────────────────────────┐
│  Server (Python)                        │
│  ├── MessageHandler (TCP 메시지 파싱)    │
│  └── CollectorGraph (LangGraph)         │
│       ├── supervisor → 라우팅            │
│       ├── discover → 화면 분석/저장      │
│       │    ├── SubtaskExtractor (LLM)   │
│       │    ├── SafetyFilter             │
│       │    ├── KeyUISelector (LLM)      │
│       │    ├── SummaryAgent (LLM)       │
│       │    └── CollectorMemory          │
│       │         ├── PageMatcher         │
│       │         ├── BundleManager       │
│       │         ├── PageStorage         │
│       │         └── ExploreMemoryAdapter│
│       └── explore_action → GREEDY 탐색   │
│            ├── HistoryAgent (LLM)       │
│            └── ExploreMemoryAdapter     │
└─────────────────────────────────────────┘
               │
          ┌────┴────┐
          ▼         ▼
   data/{app}/   memory/{app}/
   (bundle형식)  (MobileGPT-V2형식)
```

---

## 설치

### 요구사항

- Python >= 3.10, conda (권장)
- Android Studio (앱 빌드용)
- Android 13+ (API 33) 디바이스

### Server 설치

```bash
# conda 환경 생성
conda create -n mobilegpt_collector python=3.12 -y
conda activate mobilegpt_collector

# 패키지 설치
cd MobileGPT-Collector/Server
pip install -e ".[dev]"
```

### 환경변수

`Server/.env.example`을 `Server/.env`로 복사하고 API 키를 설정합니다:

```bash
cp Server/.env.example Server/.env
```

```env
# 필수
OPENAI_API_KEY=sk-...

# 선택
GEMINI_API_KEY=...
SERPAPI_KEY=...
```

### Android 앱 빌드

```bash
# Android Studio에서 app_collector/ 프로젝트 열기
# 또는 커맨드라인 빌드:
cd MobileGPT-Collector/app_collector
./gradlew assembleDebug
```

빌드된 APK: `app_collector/app/build/outputs/apk/debug/app-debug.apk`

### 서버 주소 설정

`app_collector/app/src/main/java/com/mobilegpt/collector/CollectorGlobal.java`에서 서버 IP/Port를 수정합니다:

```java
public class CollectorGlobal {
    public static final String HOST_IP = "192.168.0.9";  // 서버 IP
    public static final int HOST_PORT = 12345;            // 서버 Port
}
```

변경 후 앱을 재빌드해야 합니다.

---

## 사용법

### 1. 서버 실행

```bash
conda activate mobilegpt_collector
cd MobileGPT-Collector/Server
python -m mobilegpt_collector.main
```

서버 시작 시 IP:Port가 출력됩니다. 이 주소가 `CollectorGlobal`에 설정된 값과 일치해야 합니다.

### 2. Android 앱 설정

1. APK를 디바이스에 설치
2. 앱 실행 → 접근성 서비스 활성화 안내 다이얼로그 표시
3. 설정 > 접근성 > MobileGPT-Collector Accessibility 활성화
4. 화면 오른쪽에 플로팅 버튼 표시

### 3. 탐색 시작

1. 수집할 대상 앱을 실행
2. 플로팅 버튼 클릭 → 서브 버튼 확장
3. **Start** 버튼 클릭 → 서버 연결 + 자동 탐색 시작
4. 서버가 GREEDY 알고리즘으로 화면을 순차 탐색
5. 탐색 완료 시 자동 종료, 또는 **Finish** 버튼으로 수동 종료

### 4. 수동 캡처

자동 탐색 중에도 **Capture** 버튼으로 현재 화면을 수동 캡처할 수 있습니다.

### Server CLI 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--port` | 12345 | 서버 포트 |
| `--threshold` | 1.0 | KeyUI 매칭 임계값 (0.0~1.0) |
| `--model` | gpt-5.2 | LLM 모델 |
| `--vision` / `--no-vision` | 활성화 | 비전 모드 (스크린샷 LLM 전송) |
| `--data-dir` | ./data | 데이터 저장 경로 |
| `--reasoning-effort` | medium | LLM 추론 강도 (none/low/medium/high) |
| `--subtask-threshold` | 1.0 | Subtask 이름 overlap 임계값 (VARIANT 매칭) |
| `--memory-dir` | ./memory | MobileGPT-V2 형식 메모리 저장 경로 |

```bash
# 예시: 포트 8080, 임계값 0.8, 비전 비활성화
python -m mobilegpt_collector.main --port 8080 --threshold 0.8 --no-vision

# 예시: VARIANT 매칭 임계값 0.6, 메모리 커스텀 경로
python -m mobilegpt_collector.main --subtask-threshold 0.6 --memory-dir ./custom_memory
```

---

## TCP 프로토콜

### Client → Server

| 메시지 타입 | 포맷 | 설명 |
|------------|------|------|
| `A` | `'A' + package_name + '\n'` | 앱 패키지명 전송 |
| `S` | `'S' + size + '\n' + jpeg_bytes` | 스크린샷 전송 |
| `X` | `'X' + top_pkg + '\n' + target_pkg + '\n' + size + '\n' + xml_bytes` | 화면 XML 전송 (패키지 정보 포함) |
| `F` | `'F'` | 탐색 종료 |

- `top_pkg`: 현재 화면의 패키지명 (외부 앱 감지용)
- `target_pkg`: 탐색 대상 앱의 패키지명
- 외부 앱 감지 시 (`top_pkg != target_pkg`) 서버가 자동으로 back 액션 전송

### Server → Client

JSON 형식, `\n`으로 종료:

```json
{"name": "click", "parameters": {"index": 5, "x": 540, "y": 300, "description": "Explore 'Search'"}}
{"name": "back", "parameters": {}}
{"name": "scroll", "parameters": {"index": 2, "direction": "down"}}
{"name": "input", "parameters": {"index": 3, "input_text": "hello"}}
{"name": "finish", "parameters": {}}
```

---

## 데이터 구조

### 저장 디렉토리

```
data/
├── apps.csv                          # 앱 패키지 → 이름 매핑
├── {app_name}/
│   ├── exploration_state.json        # 탐색 상태 (resume용)
│   ├── page_registry.json            # 페이지 지식 레지스트리
│   ├── bundle_map.json               # 번들 메타데이터
│   ├── {bundle_num}/
│   │   ├── {page_num}/
│   │   │   ├── {page_num}.xml            # Raw XML
│   │   │   ├── {page_num}_parsed.xml     # Parsed XML
│   │   │   ├── {page_num}_hierarchy_parsed.xml  # Hierarchy XML
│   │   │   ├── {page_num}_encoded.xml    # Encoded XML
│   │   │   ├── {page_num}_pretty.xml     # Pretty-printed XML
│   │   │   ├── {page_num}.jpg            # 스크린샷
│   │   │   ├── subtask.json              # 서브태스크 목록
│   │   │   └── keyui.json                # KeyUI 속성
```

### MobileGPT-V2 메모리 디렉토리

수집과 동시에 MobileGPT-V2 Task mode 호환 형식으로 저장됩니다:

```
memory/
├── {app_name}/
│   ├── pages.csv                    # 페이지 레지스트리 (index, subtasks, trigger_uis, summary)
│   ├── hierarchy.csv                # 화면 구조 + OpenAI embedding
│   ├── subtask_graph.json           # Subtask Graph (nodes, edges)
│   └── pages/
│       └── {page_index}/
│           ├── available_subtasks.csv   # 가용 서브태스크 목록 (exploration 상태 포함)
│           ├── subtasks.csv             # 탐색 완료된 서브태스크 (guideline, start/end_page)
│           ├── actions.csv              # 액션 시퀀스 (action JSON, guideline)
│           └── screen/
│               ├── screenshot.jpg
│               ├── raw.xml, parsed.xml, hierarchy.xml, encoded.xml, pretty.xml
```

### XML 포맷

| 포맷 | 용도 |
|------|------|
| Raw XML | Android UI Automator 원본 |
| Parsed XML | 태그 변환 + 구조 단순화 (button/input/p/img/div/scroll) |
| Hierarchy XML | 텍스트/좌표 제거된 구조만 |
| Encoded XML | bounds/important/class 제거 (LLM 입력용) |
| Pretty XML | 사람이 읽기 위한 포맷 |

---

## 탐색 알고리즘 (GREEDY)

현재 위치에서 **가장 가까운 미탐색 서브태스크**를 우선 탐색합니다:

1. 현재 페이지에 미탐색 서브태스크가 있으면 즉시 탐색
2. 없으면 BFS로 subtask_graph를 탐색하여 최단 경로 계산
3. 경로를 따라 네비게이션 (forward/back 액션)
4. 도달 불가한 미탐색이 없으면 back으로 복귀
5. 루트에서 모든 탐색 완료 시 종료

## 페이지 매칭

| 매칭 타입 | 조건 | 동작 |
|-----------|------|------|
| EQSET | 모든 KeyUI 매칭 + 남은 UI 없음 | 기존 번들에 추가 |
| SUPERSET | threshold 이상 매칭 + 남은 UI 있음 | 기존 번들 확장 (새 서브태스크 추출) |
| SUBSET | 모든 UI 매칭 + 일부 서브태스크만 | 기존 번들에 추가 |
| **VARIANT** | **KeyUI 불일치, subtask 이름 overlap ≥ threshold, XML diff 존재** | **같은 번들의 다른 페이지로 추가** |
| NEW | threshold 미달 | 새 번들 생성 |

### VARIANT 매칭

KeyUI 속성이 변경되었지만 기능적으로 동일한 화면(subtask 이름 집합이 유사)일 때 새 번들 대신 기존 번들에 다른 페이지로 저장합니다.

- **조건 1**: encoded XML에 차이가 존재 (구조적으로 다른 화면)
- **조건 2**: subtask 이름의 Jaccard 유사도 ≥ `subtask_threshold` (기본 1.0)
- **효과**: 동적 콘텐츠나 레이아웃 변화로 KeyUI가 달라져도 불필요한 번들 생성 방지

## Safety 필터

다음 카테고리의 서브태스크는 자동 차단됩니다:

- **financial**: pay, purchase, subscribe, order, buy, checkout
- **account**: login, logout, delete_account, sign_in, sign_up
- **system**: install, uninstall, reset, format, factory_reset
- **data**: delete, clear_all, remove_all, erase
- **communication**: send, post, message, call, email

---

## 프로젝트 구조

```
MobileGPT-Collector/
├── README.md
│
├── app_collector/                  # Android 클라이언트 앱
│   ├── build.gradle                # 루트 Gradle (AGP 8.13.0)
│   ├── settings.gradle             # rootProject.name = "MobileGPT-Collector"
│   ├── gradle.properties
│   ├── gradle/wrapper/
│   └── app/
│       ├── build.gradle            # com.mobilegpt.collector, SDK 33
│       └── src/main/
│           ├── AndroidManifest.xml
│           ├── java/com/mobilegpt/collector/
│           │   ├── MainActivity.java                   # 접근성 서비스 활성화 안내
│           │   ├── CollectorAccessibilityService.java   # 핵심 접근성 서비스
│           │   ├── CollectorClient.java                 # TCP 소켓 통신
│           │   ├── CollectorGlobal.java                 # 서버 IP/Port 설정
│           │   ├── InputDispatcher.java                 # 액션 실행 (click/back/scroll/type)
│           │   ├── AccessibilityNodeInfoDumper.java     # XML 계층 캡처
│           │   ├── AccessibilityNodeInfoHelper.java     # 접근성 노드 헬퍼
│           │   ├── Utils.java                           # 유틸리티
│           │   ├── response/
│           │   │   └── GPTMessage.java                  # 서버 응답 모델
│           │   └── widgets/
│           │       └── FloatingButtonManager.java       # 플로팅 버튼 UI
│           └── res/                # 레이아웃, 드로어블, 문자열 리소스
│
└── Server/                         # Python 서버
    ├── pyproject.toml              # 패키지 설정 + 의존성
    ├── .env.example                # 환경변수 템플릿
    ├── config.py                   # CLI 인자, 기본값, 안전 카테고리
    ├── main.py                     # 엔트리포인트
    ├── server.py                   # TCP 서버 + LangGraph 통합
    ├── data/
    │   └── models.py               # Pydantic 모델
    ├── utils/
    │   ├── llm_client.py           # OpenAI/Gemini LLM 클라이언트
    │   ├── xml_parser.py           # XML 파싱 유틸리티
    │   ├── network.py              # TCP 통신 유틸리티
    │   ├── embedding.py            # OpenAI embedding + cosine similarity
    │   └── logging.py              # loguru 설정
    ├── agents/
    │   ├── subtask_extractor.py    # LLM 서브태스크 추출
    │   ├── keyui_selector.py       # LLM KeyUI 선택
    │   ├── safety_filter.py        # 위험 서브태스크 필터
    │   ├── summary_agent.py        # LLM 페이지 요약 생성
    │   ├── history_agent.py        # LLM 액션 가이드라인 생성
    │   ├── app_agent.py            # SerpAPI 앱 이름 조회
    │   └── prompts/                # LLM 프롬프트 정의
    ├── storage/
    │   ├── encoder.py              # XML 4종 변환
    │   └── page_storage.py         # 페이지 데이터 저장
    ├── matching/
    │   ├── ui_matcher.py           # UIAttributes 기반 UI 매칭
    │   ├── page_registry.py        # PageKnowledge 레지스트리 + encoded_xml 저장
    │   ├── page_matcher.py         # EQSET/SUPERSET/SUBSET/VARIANT/NEW 판정
    │   └── bundle_manager.py       # 번들 CRUD + 디스크 관리
    ├── memory/
    │   ├── collector_memory.py     # 통합 메모리 시스템
    │   ├── explore_memory.py       # MobileGPT-V2 형식 메모리 어댑터
    │   └── state_persistence.py    # 상태 영속화 (resume)
    ├── graphs/
    │   ├── state.py                # CollectorState (TypedDict)
    │   ├── collector_graph.py      # LangGraph StateGraph 정의
    │   └── nodes/
    │       ├── supervisor_node.py  # 라우팅 결정
    │       ├── discover_node.py    # 화면 분석/저장
    │       └── explore_action_node.py  # GREEDY 탐색 알고리즘
    ├── handlers/
    │   └── message_handlers.py     # TCP 메시지 핸들러
    └── tests/                      # pytest 테스트 (131개)
```

## 테스트

```bash
conda activate mobilegpt_collector
cd MobileGPT-Collector/Server

# 전체 테스트
python -m pytest tests/ -v

# 커버리지 포함
python -m pytest tests/ -v --cov=mobilegpt_collector --cov-report=term-missing
```

## 상태 영속화

탐색 중단 후 재개가 가능합니다. 탐색 상태는 자동으로 `data/{app_name}/exploration_state.json`에 저장되며, 같은 앱을 다시 탐색하면 이전 상태에서 이어서 진행합니다.

저장되는 상태:
- 방문한 페이지 목록
- 탐색/미탐색 서브태스크
- Subtask Graph (페이지 간 전이 그래프)
- 번들 매핑 정보
- 페이지 카운터

## Android 앱 상세

### 접근성 서비스 (`CollectorAccessibilityService`)

Android 접근성 프레임워크를 활용하여:
- **화면 캡처**: `AccessibilityNodeInfoDumper`로 UI 계층 XML 생성
- **스크린샷**: `takeScreenshot()` API로 JPEG 캡처
- **액션 실행**: `InputDispatcher`로 click, long-click, scroll, type, back, home 수행
- **자동 캡처**: 액션 실행 후 화면 변화 감지 시 자동 재캡처 (3~8초 타임아웃)
- **외부 앱 감지**: 현재 top window 패키지와 대상 앱 패키지 비교

### 필요 권한

| 권한 | 용도 |
|------|------|
| `INTERNET` | 서버 TCP 통신 |
| `ACCESS_NETWORK_STATE` | 네트워크 상태 확인 |
| `SYSTEM_ALERT_WINDOW` | 플로팅 버튼 오버레이 |
| `QUERY_ALL_PACKAGES` | 설치된 앱 목록 조회 |
| Accessibility Service | 화면 캡처, 제스처 수행, 스크린샷 |

### 빌드 설정

| 항목 | 값 |
|------|-----|
| Package | `com.mobilegpt.collector` |
| minSdk | 33 (Android 13) |
| targetSdk | 33 |
| compileSdk | 33 |
| AGP | 8.13.0 |
| Java | 1.8 |
