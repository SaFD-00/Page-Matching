package com.mobilegpt.collector;

import android.graphics.Bitmap;
import android.os.SystemClock;
import android.util.Log;
import android.util.Xml;
import android.view.accessibility.AccessibilityNodeInfo;

import java.io.File;
import java.io.FileOutputStream;
import java.io.FileWriter;
import java.io.IOException;
import java.io.StringWriter;
import java.util.HashMap;

import org.xmlpull.v1.XmlSerializer;

// AccessibilityNodeInfo를 XML로 덤프하는 클래스
public class AccessibilityNodeInfoDumper {
    private static int screen_num = 0; // 화면 번호 (파일 저장 시 사용)
    private static final String TAG = "MobileGPT_XMLDumper"; // 로그 태그
    // NAF(Not Accessibility Friendly) 검사에서 제외할 클래스 목록
    private static final String[] NAF_EXCLUDED_CLASSES = new String[] {
            android.widget.GridView.class.getName(), android.widget.GridLayout.class.getName(),
            android.widget.ListView.class.getName(), android.widget.TableLayout.class.getName()
    };

    /**
     * AccessibilityNodeInfo를 사용하여 레이아웃 계층을 탐색하고
     * 지정된 위치에 XML 덤프를 생성합니다.
     * @param root 루트 노드
     * @param nodeMap 노드를 인덱스와 함께 저장할 맵
     * @param baseDir 파일을 저장할 기본 디렉토리
     * @return 생성된 XML 문자열
     */
    public static String dumpWindow(AccessibilityNodeInfo root, HashMap<Integer, AccessibilityNodeInfo> nodeMap, File baseDir) {
        if (root == null) {
            Log.d(TAG, "루트 노드가 null입니다!");
            return null;
        }
        final long startTime = SystemClock.uptimeMillis();
        try {
            XmlSerializer serializer = Xml.newSerializer();
            StringWriter stringWriter = new StringWriter();
            serializer.setOutput(stringWriter);
            serializer.startDocument("UTF-8", true);
            serializer.startTag("", "hierarchy"); // 최상위 'hierarchy' 태그 시작
            dumpNodeRec(root, serializer, nodeMap, nodeMap.size()); // 재귀적으로 노드 덤프
            serializer.endTag("", "hierarchy");
            serializer.endDocument();
            final long endTime = SystemClock.uptimeMillis();
            Log.w(TAG, "가져오기 시간: " + (endTime - startTime) + "ms");
            String xml = stringWriter.toString();
//            dumpWindowToFile(xml, baseDir); // 파일로 덤프 (현재 주석 처리됨)
            return xml;
        } catch (IOException e) {
            Log.e(TAG, "창을 문자열로 덤프하는 데 실패했습니다.", e);
            return null;
        }
    }

    // XML을 파일에 저장하는 메서드
    private static void dumpWindowToFile(String xml, File baseDir) {
        File dumpFile = new File(baseDir, screen_num+".txt");
        try {
            FileWriter writer = new FileWriter(dumpFile);
            writer.write(xml);
            writer.close();


            screen_num ++;
        } catch (IOException e) {
            Log.e(TAG, "창을 파일로 덤프하는 데 실패했습니다.", e);
        }
    }

    // 비트맵 이미지를 파일로 저장하는 메서드
    public static void saveImage(Bitmap bitmap, File baseDir) {
        File file = new File( baseDir, screen_num+".jpg");
        FileOutputStream out = null;
        try {
            out = new FileOutputStream(file);
            bitmap.compress(Bitmap.CompressFormat.JPEG, 100, out); // JPEG 형식으로 압축
            out.flush();
            out.close();
        } catch (Exception e) {
            Log.e(TAG, "스크린샷 저장에 실패했습니다.");
        }
    }

    // 노드를 재귀적으로 탐색하며 XML로 변환하는 메서드
    private static void dumpNodeRec(AccessibilityNodeInfo node, XmlSerializer serializer,
                                    HashMap<Integer, AccessibilityNodeInfo> nodeMap, int index) throws IOException {
        nodeMap.put(index, node); // 현재 노드를 맵에 추가
        serializer.startTag("", "node");
        // 접근성 친화적이지 않은 경우 'NAF' 속성 추가
        if (!nafExcludedClass(node) && !nafCheck(node))
            serializer.attribute("", "NAF", Boolean.toString(true));
        // 다양한 노드 속성들을 XML 속성으로 추가
        serializer.attribute("", "resource-id",safeCharSeqToString(node.getViewIdResourceName()));
        serializer.attribute("", "important", Boolean.toString(node.isImportantForAccessibility()));
        serializer.attribute("", "index",Integer.toString(index));
        serializer.attribute("", "text", safeCharSeqToString(node.getText()));
        serializer.attribute("", "class", safeCharSeqToString(node.getClassName()));
        serializer.attribute("", "content-desc", safeCharSeqToString(node.getContentDescription()));
        serializer.attribute("", "checkable", Boolean.toString(node.isCheckable()));
        serializer.attribute("", "checked", Boolean.toString(node.isChecked()));
        serializer.attribute("", "clickable", Boolean.toString(node.isClickable()));
        serializer.attribute("", "enabled", Boolean.toString(node.isEnabled()));
        serializer.attribute("", "scrollable", Boolean.toString(node.isScrollable()));
        serializer.attribute("", "long-clickable", Boolean.toString(node.isLongClickable()));
        serializer.attribute("", "selected", Boolean.toString(node.isSelected()));
        serializer.attribute("", "bounds",
                AccessibilityNodeInfoHelper.getVisibleBoundsInScreen(node).toShortString());
        int count = node.getChildCount();
        // 자식 노드들을 재귀적으로 처리
        for (int i = 0; i < count; i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child != null) {
                if (child.isVisibleToUser()) {
                    dumpNodeRec(child, serializer, nodeMap, nodeMap.size());
                } else {
//                    Log.d(TAG, String.format("Skipping invisible child: %s", child.toString()));
                }
            } else {
                Log.d(TAG, String.format("Null child %d/%d, parent: %s",
                        i, count, node.toString()));
            }
        }
        serializer.endTag("", "node");
    }

    /**
     * 제외할 클래스 목록이 완전하지 않을 수 있습니다. 우리는 단지
     * 클릭 가능하고 활성화된 것으로 잘못 구성될 수 있는 표준 레이아웃 클래스의 노이즈를
     * 줄이려고 시도하고 있습니다.
     *
     * @param n 검사할 노드
     * @return 제외 대상 클래스이면 true
     */
    private static boolean nafExcludedClass(AccessibilityNodeInfo n) {
        String className = safeCharSeqToString(n.getClassName());
        for(String excludedClassName : NAF_EXCLUDED_CLASSES) {
            if(className.endsWith(excludedClassName))
                return true;
        }
        return false;
    }

    /**
     * 활성화되고 클릭 가능하지만 텍스트나 콘텐츠 설명이 없는 UI 컨트롤을 찾습니다.
     * 이러한 컨트롤 구성은 대화형 컨트롤이 UI에 존재하지만 접근성 친화적이지 않을 가능성이 높다는 것을 나타냅니다.
     * 여기서는 이러한 컨트롤을 NAF(Not Accessibility Friendly) 컨트롤이라고 합니다.
     *
     * @param node 검사할 노드
     * @return 노드가 검사를 통과하지 못하면 false, 모두 정상이면 true
     */
    private static boolean nafCheck(AccessibilityNodeInfo node) {
        boolean isNaf = node.isClickable() && node.isEnabled()
                && safeCharSeqToString(node.getContentDescription()).isEmpty()
                && safeCharSeqToString(node.getText()).isEmpty();

        if (!isNaf)
            return true;

        // 컨테이너 요소가 클릭 가능하고 NAF이지만 자식의 텍스트나 설명이 사용 가능한 경우가 있으므로
        // 자식 노드를 확인합니다. 이러한 레이아웃은 괜찮은 것으로 간주합니다.
        return childNafCheck(node);
    }

    /**
     * 이 메서드는 노드가 이미 NAF로 결정되었고 자식에 대한 추가 검사가 필요한 경우에 사용해야 합니다.
     * 노드는 LinearLayout과 같은 컨테이너일 수 있으며 클릭 가능하도록 설정되었지만 텍스트나 콘텐츠 설명이 없을 수 있습니다.
     * 그러나 자식 중 하나 이상이 텍스트 또는 콘텐츠 설명을 채워 접근성 친화 요구 사항을 충족할 것으로 예상합니다.
     * 이러한 조합은 이 덤퍼에서 접근성에 대해 허용 가능한 것으로 간주됩니다.
     *
     * @param node 검사할 노드
     * @return 자식 중 하나가 접근성 요구 사항을 충족하면 true
     */
    private static boolean childNafCheck(AccessibilityNodeInfo node) {
        int childCount = node.getChildCount();
        for (int x = 0; x < childCount; x++) {
            AccessibilityNodeInfo childNode = node.getChild(x);

            if (!safeCharSeqToString(childNode.getContentDescription()).isEmpty()
                    || !safeCharSeqToString(childNode.getText()).isEmpty())
                return true;

            if (childNafCheck(childNode))
                return true;
        }
        return false;
    }

    // CharSequence를 안전하게 String으로 변환 (null 처리)
    private static String safeCharSeqToString(CharSequence cs) {
        if (cs == null)
            return "";
        else {
            return stripInvalidXMLChars(cs);
        }
    }

    // XML에 유효하지 않은 문자를 제거하거나 대체하는 메서드
    private static String stripInvalidXMLChars(CharSequence cs) {
        StringBuffer ret = new StringBuffer();
        char ch;
        /* http://www.w3.org/TR/xml11/#charsets
        [#x1-#x8], [#xB-#xC], [#xE-#x1F], [#x7F-#x84], [#x86-#x9F], [#xFDD0-#xFDDF],
        [#x1FFFE-#x1FFFF], [#x2FFFE-#x2FFFF], [#x3FFFE-#x3FFFF],
        [#x4FFFE-#x4FFFF], [#x5FFFE-#x5FFFF], [#x6FFFE-#x6FFFF],
        [#x7FFFE-#x7FFFF], [#x8FFFE-#x8FFFF], [#x9FFFE-#x9FFFF],
        [#xAFFFE-#xAFFFF], [#xBFFFE-#xBFFFF], [#xCFFFE-#xCFFFF],
        [#xDFFFE-#xDFFFF], [#xEFFFE-#xEFFFF], [#xFFFFE-#xFFFFF],
        [#x10FFFE-#x10FFFF].
         */
        for (int i = 0; i < cs.length(); i++) {
            ch = cs.charAt(i);

            if((ch >= 0x1 && ch <= 0x8) || (ch >= 0xB && ch <= 0xC) || (ch >= 0xE && ch <= 0x1F) ||
                    (ch >= 0x7F && ch <= 0x84) || (ch >= 0x86 && ch <= 0x9f) ||
                    (ch >= 0xFDD0 && ch <= 0xFDDF) || (ch >= 0x1FFFE && ch <= 0x1FFFF) ||
                    (ch >= 0x2FFFE && ch <= 0x2FFFF) || (ch >= 0x3FFFE && ch <= 0x3FFFF) ||
                    (ch >= 0x4FFFE && ch <= 0x4FFFF) || (ch >= 0x5FFFE && ch <= 0x5FFFF) ||
                    (ch >= 0x6FFFE && ch <= 0x6FFFF) || (ch >= 0x7FFFE && ch <= 0x7FFFF) ||
                    (ch >= 0x8FFFE && ch <= 0x8FFFF) || (ch >= 0x9FFFE && ch <= 0x9FFFF) ||
                    (ch >= 0xAFFFE && ch <= 0xAFFFF) || (ch >= 0xBFFFE && ch <= 0xBFFFF) ||
                    (ch >= 0xCFFFE && ch <= 0xCFFFF) || (ch >= 0xDFFFE && ch <= 0xDFFFF) ||
                    (ch >= 0xEFFFE && ch <= 0xEFFFF) || (ch >= 0xFFFFE && ch <= 0xFFFFF) ||
                    (ch >= 0x10FFFE && ch <= 0x10FFFF))
                ret.append(".");
            else
                ret.append(ch);
        }
        return ret.toString();
    }


}
