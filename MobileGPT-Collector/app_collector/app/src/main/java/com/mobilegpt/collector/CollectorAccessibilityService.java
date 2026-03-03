package com.mobilegpt.collector;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.content.ClipboardManager;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Rect;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.Display;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.IOException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import android.view.accessibility.AccessibilityWindowInfo;

import androidx.annotation.NonNull;

import com.mobilegpt.collector.widgets.FloatingButtonManager;
import com.mobilegpt.collector.response.GPTMessage;

public class CollectorAccessibilityService extends AccessibilityService {
    private static final String TAG = "MobileGPT_Service";

    // Excluded packages (MobileGPT apps that should not be considered as top window)
    private static final String[] EXCLUDED_PACKAGES = {
        "com.mobilegpt.collector",  // App_Auto_Explorer
        "com.example.MobileGPT",        // App
        "com.example.hardcode"          // App_Explorer
    };

    private CollectorClient mClient;
    public FloatingButtonManager mFloatingButtonManager;
    private HashMap<Integer, AccessibilityNodeInfo> nodeMap;
    private String targetPackageName;
    private String finalTargetPackageName;
    private ExecutorService mExecutorService;
    private final Handler mainThreadHandler = new Handler(Looper.getMainLooper());
    private String currentScreenXML = "";
    private Bitmap currentScreenShot = null;
    private File fileDirectory;

    private boolean autoExploreMode = false;
    private boolean xmlPending = false;
    private boolean screenNeedUpdate = false;
    private Runnable screenUpdateWaitRunnable;
    private Runnable screenUpdateTimeoutRunnable;
    private Runnable clickRetryRunnable;

    // Current top window package (updated in saveCurrScreenXML)
    private String currentTopPackage = null;

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (event.getEventType() == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            CharSequence packageName = event.getPackageName();
            if (packageName != null && !packageName.equals("com.mobilegpt.collector")) {
                targetPackageName = packageName.toString();
            }
        }

        if (autoExploreMode &&
            (event.getEventType() == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED ||
             event.getEventType() == AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED) &&
            event.getSource() != null) {

            if (event.getPackageName() != null && event.getPackageName().equals("com.mobilegpt.collector")) {
                return;
            }

            if (xmlPending && screenNeedUpdate) {
                mainThreadHandler.removeCallbacks(clickRetryRunnable);
                mainThreadHandler.removeCallbacks(screenUpdateWaitRunnable);
                mainThreadHandler.removeCallbacks(screenUpdateTimeoutRunnable);
                mainThreadHandler.postDelayed(screenUpdateWaitRunnable, 3000);
                screenNeedUpdate = false;
            }
        }
    }

    @Override
    public void onServiceConnected() {
        AccessibilityServiceInfo info = new AccessibilityServiceInfo();

        info.eventTypes = AccessibilityEvent.TYPES_ALL_MASK;
        info.feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
                | AccessibilityServiceInfo.FEEDBACK_HAPTIC;
        info.notificationTimeout = 100;
        info.flags = AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS
                | AccessibilityServiceInfo.CAPABILITY_CAN_PERFORM_GESTURES
                | AccessibilityServiceInfo.CAPABILITY_CAN_TAKE_SCREENSHOT
                | AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS
                | AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS;

        mExecutorService = Executors.newSingleThreadExecutor();

        mFloatingButtonManager = new FloatingButtonManager(this, mClient);
        mFloatingButtonManager.show();

        screenUpdateWaitRunnable = () -> {
            Log.d(TAG, "Screen update wait complete, starting auto capture");
            mainThreadHandler.removeCallbacks(screenUpdateTimeoutRunnable);
            autoCapture();
        };

        screenUpdateTimeoutRunnable = () -> {
            Log.d(TAG, "Screen update timeout, starting auto capture");
            mainThreadHandler.removeCallbacks(screenUpdateWaitRunnable);
            autoCapture();
        };
    }

    /**
     * Check if a package is a MobileGPT app (should be excluded from top window).
     */
    private boolean isMobileGPTPackage(String packageName) {
        if (packageName == null) return false;
        for (String excluded : EXCLUDED_PACKAGES) {
            if (packageName.equals(excluded)) {
                return true;
            }
        }
        return false;
    }

    private String windowTypeToString(int type) {
        switch (type) {
            case AccessibilityWindowInfo.TYPE_APPLICATION: return "APPLICATION";
            case AccessibilityWindowInfo.TYPE_INPUT_METHOD: return "INPUT_METHOD";
            case AccessibilityWindowInfo.TYPE_SYSTEM: return "SYSTEM";
            case AccessibilityWindowInfo.TYPE_ACCESSIBILITY_OVERLAY: return "ACCESSIBILITY_OVERLAY";
            default: return "UNKNOWN(" + type + ")";
        }
    }

    /**
     * Get the top interactable window's root, excluding MobileGPT apps and system UI.
     * Returns the first application window, which may be an overlay or external app.
     */
    private AccessibilityNodeInfo getTopInteractableRoot() {
        List<AccessibilityWindowInfo> windows = getWindows();

        Log.d(TAG, "=== Window Debug: Total windows = " + windows.size() + " ===");
        for (int i = 0; i < windows.size(); i++) {
            AccessibilityWindowInfo window = windows.get(i);
            int type = window.getType();
            boolean focused = window.isFocused();
            boolean active = window.isActive();
            AccessibilityNodeInfo root = window.getRoot();
            String pkgName = (root != null && root.getPackageName() != null)
                    ? root.getPackageName().toString() : "null";

            Log.d(TAG, String.format("  [%d] type=%s, focused=%b, active=%b, pkg=%s, root=%s",
                    i, windowTypeToString(type), focused, active, pkgName,
                    (root != null ? "OK" : "NULL")));
        }
        Log.d(TAG, "=== End Window Debug ===");

        for (AccessibilityWindowInfo window : windows) {
            // Only consider application windows (skip SystemUI, IME, etc.)
            if (window.getType() != AccessibilityWindowInfo.TYPE_APPLICATION) {
                continue;
            }

            AccessibilityNodeInfo root = window.getRoot();
            if (root == null) continue;

            CharSequence pkgName = root.getPackageName();
            if (pkgName == null) continue;

            String pkg = pkgName.toString();

            if (!isMobileGPTPackage(pkg)) {
                Log.d(TAG, "Top interactable window: " + pkg + " (type: APPLICATION)");
                return root;
            }
        }

        Log.d(TAG, "No interactable window found");
        return null;
    }

    public void start() {
        reset();
        autoExploreMode = true;
        xmlPending = false;
        screenNeedUpdate = false;
        mExecutorService.execute(this::initNetworkConnection);
        mExecutorService.execute(() -> mClient.sendPackageName(targetPackageName));
        finalTargetPackageName = targetPackageName;
        Log.d(TAG, "Auto explore mode started");
    }

    public void finish() {
        mExecutorService.execute(() -> mClient.sendFinish());
        mFloatingButtonManager.shrink();
    }

    public void captureScreen() {
        Log.d(TAG, "Manual capture triggered");
        mFloatingButtonManager.dismiss();
        saveCurrScreenXML();
        saveCurrentScreenShot();
    }

    private void autoCapture() {
        Log.d(TAG, "Auto capture triggered");
        xmlPending = false;
        screenNeedUpdate = false;
        saveCurrScreenXML();
        saveCurrentScreenShot();
    }

    private void saveCurrScreenXML() {
        nodeMap = new HashMap<>();
        Log.d(TAG, "Node map renewed");

        AccessibilityNodeInfo topRoot = getTopInteractableRoot();

        if (topRoot == null) {
            Log.e(TAG, "No interactable window found");
            currentScreenXML = "";
            currentTopPackage = null;
            return;
        }

        currentTopPackage = topRoot.getPackageName().toString();
        Log.d(TAG, "Top: " + currentTopPackage + ", Target: " + finalTargetPackageName);

        currentScreenXML = AccessibilityNodeInfoDumper.dumpWindow(
            topRoot, nodeMap, fileDirectory
        );
    }

    private void saveCurrentScreenShot() {
        takeScreenshot(Display.DEFAULT_DISPLAY, getMainExecutor(), new TakeScreenshotCallback() {
            @Override
            public void onSuccess(@NonNull ScreenshotResult screenshotResult) {
                Log.d(TAG, "Screenshot success");
                currentScreenShot = Bitmap.wrapHardwareBuffer(screenshotResult.getHardwareBuffer(), screenshotResult.getColorSpace());
                sendScreen();
                mFloatingButtonManager.show();
            }

            @Override
            public void onFailure(int i) {
                Log.i(TAG, "Screenshot failed, code: " + i);
            }
        });
    }

    private void sendScreen() {
        mExecutorService.execute(() -> mClient.sendScreenshot(currentScreenShot));
        mExecutorService.execute(() -> mClient.sendXMLWithPackage(
            currentScreenXML,
            currentTopPackage != null ? currentTopPackage : "",
            finalTargetPackageName != null ? finalTargetPackageName : ""
        ));
    }

    @Override
    public void onInterrupt() {
        Log.e(TAG, "OnInterrupt");
    }

    @Override
    public void onDestroy() {
        mClient.disconnect();
        mClient = null;
        super.onDestroy();
    }

    private void reset() {
        if (mClient != null) {
            mClient.disconnect();
            mClient = null;
        }
    }

    private void initNetworkConnection() {
        mClient = new CollectorClient(CollectorGlobal.HOST_IP, CollectorGlobal.HOST_PORT);
        try {
            mClient.connect();
            mClient.receiveMessages(message -> {
                new Thread(() -> {
                    if (message != null) {
                        handleResponse(message);
                    }
                }).start();
            });
        } catch (IOException e) {
            Log.e(TAG, "Server offline");
        }
    }

    private void handleResponse(String message) {
        Log.d(TAG, "Received message: " + message);

        try {
            GPTMessage gptMessage = new GPTMessage(message);
            String action = gptMessage.getActionName();
            JSONObject args = gptMessage.getArgs();

            if (action.equals("retry")) {
                Log.d(TAG, "Retry requested, recapturing after delay");
                mainThreadHandler.postDelayed(() -> autoCapture(), 500);
                return;
            } else if (action.equals("back")) {
                Log.d(TAG, "Performing back action");
                InputDispatcher.performBack(this);
                screenNeedUpdate = true;
                xmlPending = true;
                mainThreadHandler.postDelayed(screenUpdateTimeoutRunnable, 5000);
                return;
            } else if (action.equals("home")) {
                Log.d(TAG, "Performing home action");
                InputDispatcher.performHome(this);
                screenNeedUpdate = true;
                xmlPending = true;
                mainThreadHandler.postDelayed(screenUpdateTimeoutRunnable, 5000);
                return;
            }

            int index = -1;
            try {
                index = Integer.parseInt((String) (args.get("index")));
            } catch (ClassCastException e) {
                index = (Integer) args.get("index");
            } catch (JSONException e) {
                Log.e(TAG, "No index in action");
                return;
            }

            AccessibilityNodeInfo targetNode = nodeMap.get(index);

            if (targetNode == null) {
                Log.e(TAG, "No node found for index " + index);
                Log.d(TAG, "Available nodeMap indices:");
                for (Map.Entry<Integer, AccessibilityNodeInfo> entry : nodeMap.entrySet()) {
                    Integer key = entry.getKey();
                    AccessibilityNodeInfo node = entry.getValue();
                    Rect nodeBound = new Rect();
                    node.getBoundsInScreen(nodeBound);
                    Log.d(TAG, "Index: " + key + " - Bound: [" + nodeBound.left + "," + nodeBound.top + "," + nodeBound.right + "," + nodeBound.bottom + "]");
                }
                return;
            }

            boolean actionSuccess = false;
            final int finalIndex = index;
            final AccessibilityNodeInfo finalTargetNode = targetNode;

            switch (action) {
                case "click":
                    Log.d(TAG, "Performing click on index " + finalIndex);
                    actionSuccess = InputDispatcher.performClick(this, targetNode, false);
                    Log.d(TAG, "Click success=" + actionSuccess);

                    clickRetryRunnable = () -> InputDispatcher.performClick(CollectorAccessibilityService.this, finalTargetNode, true);
                    mainThreadHandler.postDelayed(clickRetryRunnable, 3000);
                    break;

                case "long-click":
                    Log.d(TAG, "Performing long-click on index " + finalIndex);
                    actionSuccess = InputDispatcher.performLongClick(this, targetNode);
                    Log.d(TAG, "Long-click success=" + actionSuccess);
                    break;

                case "input":
                    Log.d(TAG, "Performing input on index " + finalIndex);
                    String text = (String) (args.get("input_text"));
                    ClipboardManager clipboard = (ClipboardManager) this.getSystemService(Context.CLIPBOARD_SERVICE);
                    actionSuccess = InputDispatcher.performTextInput(this, clipboard, targetNode, text);
                    Log.d(TAG, "Input success=" + actionSuccess);
                    break;

                case "scroll":
                    Log.d(TAG, "Performing scroll on index " + finalIndex);
                    String direction = (String) (args.get("direction"));
                    actionSuccess = InputDispatcher.performScroll(targetNode, direction);
                    Log.d(TAG, "Scroll success=" + actionSuccess);
                    break;
            }

            screenNeedUpdate = true;
            xmlPending = true;
            mainThreadHandler.postDelayed(screenUpdateTimeoutRunnable, 8000);

        } catch (JSONException e) {
            Log.e(TAG, "Action JSON parsing error: " + e.getMessage());
            e.printStackTrace();
        }
    }
}
