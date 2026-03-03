package com.mobilegpt.collector;

import android.graphics.Rect;
import android.view.accessibility.AccessibilityNodeInfo;

// AccessibilityNodeInfo와 관련된 헬퍼(도우미) 클래스
public class AccessibilityNodeInfoHelper {
    /**
     * 노드의 경계를 화면 크기에 맞게 잘라낸 값을 반환합니다.
     * (현재는 화면 크기에 맞춰 잘라내는 코드는 주석 처리되어 있습니다.)
     *
     * @param node 경계를 가져올 노드
     * @return 노드가 null이면 null, 그렇지 않으면 보이는 경계를 담은 Rect 객체
     */
    static Rect getVisibleBoundsInScreen(AccessibilityNodeInfo node) {
        if (node == null) {
            return null;
        }
        // 대상 노드의 화면 내 경계를 저장할 Rect 객체
        Rect nodeRect = new Rect();
        node.getBoundsInScreen(nodeRect);

//        // 화면 전체 크기를 나타내는 Rect
//        Rect displayRect = new Rect();
//        Point outSize = new Point();
//        display.getSize(outSize);
//        displayRect.top = 0;
//        displayRect.left = 0;
//        displayRect.right = outSize.x;
//        displayRect.bottom = outSize.y;
//
//        // 노드의 경계와 화면 경계의 교차 부분을 계산 (화면 밖으로 나가는 부분 잘라내기)
//        nodeRect.intersect(displayRect);
        return nodeRect;
    }
}
