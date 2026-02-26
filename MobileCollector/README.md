# MobileCollector

KeyUI 기반 자동 모바일 앱 화면 데이터 수집기.

Android 앱을 자동 탐색하면서 화면을 수집하고, KeyUI 매칭으로 유사 화면을 동일 번들로 그룹핑합니다.

## 개요

MobileCollector는 **Android 클라이언트 앱**과 **Python 서버** 두 컴포넌트로 구성됩니다:

1. **app_collector** (Android): 접근성 서비스로 화면 XML/스크린샷을 캡처하여 서버에 전송하고, 서버의 액션 명령을 실행
2. **Server** (Python): LangGraph 기반 GREEDY 탐색으로 앱을 자동 탐색하며, KeyUI 매칭으로 유사 화면을 분류/저장

### 처리 파이프라인

1. **화면 수신**: Android 클라이언트(app_collector)로부터 XML + 스크린샷 수신
2. **Subtask 추출**: LLM으로 화면에서 수행 가능한 서브태스크 추출
3. **Safety 필터링**: 위험한 서브태스크 (결제, 삭제, 로그인 등) 자동 차단
4. **KeyUI 선택**: 각 서브태스크를 대표하는 UI 요소 (KeyUI) 선택
5. **페이지 매칭**: KeyUI 속성 비교로 기존 번들과 유사도 판정 (EQSET/SUPERSET/SUBSET/VARIANT/NEW)
6. **데이터 저장**: MobileCollector 포맷 + MobileGPT-V2 메모리 포맷 동시 저장
7. **GREEDY 탐색**: BFS 기반 최단 경로로 미탐색 서브태스크를 순차 탐색
8. **메모리 파이프라인**: 수집 데이터를 MobileGPT-V2 Task mode에서 바로 사용 가능한 형식으로 저장

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
conda create -n mobilecollector python=3.12 -y
conda activate mobilecollector

# 패키지 설치
cd MobileCollector/Server
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
cd MobileCollector/app_collector
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
conda activate mobilecollector
cd MobileCollector/Server
python -m mobilecollector.main
```

서버 시작 시 IP:Port가 출력됩니다. 이 주소가 `CollectorGlobal`에 설정된 값과 일치해야 합니다.

### 2. Android 앱 설정

1. APK를 디바이스에 설치
2. 앱 실행 → 접근성 서비스 활성화 안내 다이얼로그 표시
3. 설정 > 접근성 > MobileCollector Accessibility 활성화
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
| `--subtask-threshold` | 0.7 | Subtask 이름 overlap 임계값 (VARIANT 매칭) |
| `--memory-dir` | ./memory | MobileGPT-V2 형식 메모리 저장 경로 |

```bash
# 예시: 포트 8080, 임계값 0.8, 비전 비활성화
python -m mobilecollector.main --port 8080 --threshold 0.8 --no-vision

# 예시: VARIANT 매칭 임계값 0.6, 메모리 커스텀 경로
python -m mobilecollector.main --subtask-threshold 0.6 --memory-dir ./custom_memory
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
- **조건 2**: subtask 이름의 Jaccard 유사도 ≥ `subtask_threshold` (기본 0.7)
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
MobileCollector/
├── README.md
│
├── app_collector/                  # Android 클라이언트 앱
│   ├── build.gradle                # 루트 Gradle (AGP 8.13.0)
│   ├── settings.gradle             # rootProject.name = "MobileCollector"
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
conda activate mobilecollector
cd MobileCollector/Server

# 전체 테스트
python -m pytest tests/ -v

# 커버리지 포함
python -m pytest tests/ -v --cov=mobilecollector --cov-report=term-missing
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
