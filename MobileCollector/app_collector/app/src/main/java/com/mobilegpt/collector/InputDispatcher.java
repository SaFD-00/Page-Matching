package com.mobilegpt.collector;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.content.ClipboardManager;
import android.graphics.Path;
import android.graphics.Rect;
import android.os.Bundle;
import android.util.Log;
import android.view.accessibility.AccessibilityNodeInfo;

public class InputDispatcher {
    private static final String TAG = "MobileGPT_InputDispatcher";

    private static AccessibilityService.GestureResultCallback callback = new AccessibilityService.GestureResultCallback() {
        @Override
        public void onCompleted(GestureDescription gestureDescription) {
            super.onCompleted(gestureDescription);
            Log.d(TAG, "Gesture completed");
        }

        @Override
        public void onCancelled(GestureDescription gestureDescription) {
            super.onCancelled(gestureDescription);
            Log.d(TAG, "Gesture cancelled");
        }
    };

    public static boolean performClick(AccessibilityService service, AccessibilityNodeInfo node, boolean retry) {
        AccessibilityNodeInfo targetNode = nearestClickableNode(node);
        if (targetNode != null) {
            Rect nodeBound = new Rect();
            targetNode.getBoundsInScreen(nodeBound);
            Log.d(TAG, "Node Bound: left=" + nodeBound.left + " top=" + nodeBound.top + " right=" + nodeBound.right + " bottom=" + nodeBound.bottom);
            if (!retry)
                return targetNode.performAction(AccessibilityNodeInfo.ACTION_CLICK);
            else
                return InputDispatcher.dispatchClick(service, (int) ((nodeBound.left + nodeBound.right) / 2), (int) ((nodeBound.top + nodeBound.bottom) / 2), 10);
        } else {
            Log.e(TAG, "No matching UI to click. Force touch event.");
            Rect nodeBound = new Rect();
            node.getBoundsInScreen(nodeBound);
            Log.d(TAG, "Node Bound: left=" + nodeBound.left + " top=" + nodeBound.top + " right=" + nodeBound.right + " bottom=" + nodeBound.bottom);
            return InputDispatcher.dispatchClick(service, (int) ((nodeBound.left + nodeBound.right) / 2), (int) ((nodeBound.top + nodeBound.bottom) / 2), 10);
        }
    }

    public static boolean performLongClick(AccessibilityService service, AccessibilityNodeInfo node) {
        AccessibilityNodeInfo targetNode = nearestLongClickableNode(node);
        if (targetNode != null) {
            return targetNode.performAction(AccessibilityNodeInfo.ACTION_LONG_CLICK);
        } else {
            Log.e(TAG, "No matching UI to long-click. Force long touch event.");
            Rect nodeBound = new Rect();
            node.getBoundsInScreen(nodeBound);
            return InputDispatcher.dispatchClick(service, (int) ((nodeBound.left + nodeBound.right) / 2), (int) ((nodeBound.top + nodeBound.bottom) / 2), 2000);
        }
    }

    public static boolean performScroll(AccessibilityNodeInfo node, String direction) {
        AccessibilityNodeInfo targetNode = nearestScrollableNode(node);
        if (targetNode != null) {
            if (direction.equals("down"))
                return targetNode.performAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD);
            else
                return targetNode.performAction(AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD);
        } else {
            Log.e(TAG, "No scrollable UI found");
            return false;
        }
    }

    public static boolean performTextInput(AccessibilityService service, ClipboardManager clipboard, AccessibilityNodeInfo node, String text) {
        if (node.isEditable()) {
            Bundle arguments = new Bundle();
            arguments.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
            return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments);
        } else {
            return performClick(service, node, false);
        }
    }

    public static boolean performBack(AccessibilityService service) {
        return service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK);
    }

    public static boolean performHome(AccessibilityService service) {
        return service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME);
    }

    public static boolean dispatchClick(AccessibilityService service, float x, float y, int duration) {
        Log.d(TAG, String.format("Click gesture for x=%f y=%f", x, y));
        boolean result = service.dispatchGesture(createClick(x, y, duration), callback, null);
        Log.d(TAG, "Gesture dispatched: " + result);
        return result;
    }

    private static AccessibilityNodeInfo nearestClickableNode(AccessibilityNodeInfo node) {
        if (node == null)
            return null;

        if (node.isClickable()) {
            return node;
        } else {
            return null;
        }
    }

    private static AccessibilityNodeInfo nearestLongClickableNode(AccessibilityNodeInfo node) {
        if (node == null)
            return null;

        if (node.isLongClickable()) {
            return node;
        } else {
            return null;
        }
    }

    private static AccessibilityNodeInfo nearestScrollableNode(AccessibilityNodeInfo node) {
        if (node == null)
            return null;

        if (node.isScrollable()) {
            return node;
        } else {
            return nearestScrollableNode(node.getParent());
        }
    }

    private static GestureDescription createClick(float x, float y, int duration) {
        Path clickPath = new Path();
        clickPath.moveTo(x, y);
        GestureDescription.StrokeDescription clickStroke =
                new GestureDescription.StrokeDescription(clickPath, 0, duration);
        GestureDescription.Builder clickBuilder = new GestureDescription.Builder();
        clickBuilder.addStroke(clickStroke);
        return clickBuilder.build();
    }
}
