package com.mobilegpt.collector;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;

import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.Intent;
import android.os.Build;
import android.provider.Settings;
import android.util.Log;
import android.view.View;

import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;

import android.Manifest;

// 앱의 메인 액티비티: 앱 시작 시 가장 먼저 실행되는 화면입니다.
public class MainActivity extends AppCompatActivity {
    private static final String TAG = "MobileGPT(MainActivity)"; // 로그 태그

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // 접근성 권한이 없는 경우, 권한을 요청하는 다이얼로그를 표시합니다.
        if(!checkAccessibilityPermissions()) {
            Log.d(TAG, "접근성 권한이 거부되었습니다.");
            setAccessibilityPermissions();
        }
    }

    // 접근성 권한이 있는지 확인하는 메서드
    // 권한이 있으면 true, 없으면 false를 반환합니다.
    public boolean checkAccessibilityPermissions() {
        int accessibilityEnabled = 0;
        // 검사할 접근성 서비스 이름
        final String service = getPackageName() + "/" + "com.mobilegpt.collector.CollectorAccessibilityService";

        try {
            // 시스템 설정에서 접근성 활성화 상태를 가져옵니다.
            accessibilityEnabled = Settings.Secure.getInt(
                    getApplicationContext().getContentResolver(),
                    android.provider.Settings.Secure.ACCESSIBILITY_ENABLED);
        } catch (Settings.SettingNotFoundException e) {
            // 설정 값을 찾지 못한 경우 (접근성이 비활성화된 상태)
        }

        if (accessibilityEnabled == 1) {
            // 활성화된 접근성 서비스 목록을 가져옵니다.
            String settingValue = Settings.Secure.getString(
                    getApplicationContext().getContentResolver(),
                    Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
            if (settingValue != null) {
                // 콜론(:)으로 구분된 서비스 목록을 분리합니다.
                String[] services = settingValue.split(":");
                for (String enabledService : services) {
                    // 현재 앱의 접근성 서비스가 목록에 있는지 확인합니다.
                    if (enabledService.equalsIgnoreCase(service)) {
                        return true;
                    }
                }
            }
        }
        return false;
    }

    // 접근성 권한 설정을 요청하는 다이얼로그를 표시하는 메서드
    public void setAccessibilityPermissions() {
        AlertDialog.Builder gsDialog = new AlertDialog.Builder(this);
        gsDialog.setTitle("접근성 권한 설정");
        gsDialog.setMessage("앱의 원활한 작동을 위해 접근성 권한이 필요합니다.");
        gsDialog.setPositiveButton("확인", new DialogInterface.OnClickListener() {
            public void onClick(DialogInterface dialog, int which) {
                // '확인' 버튼 클릭 시 접근성 설정 화면으로 이동합니다.
                Intent intent = new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS);
                intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(intent);
                return;
            }
        }).create().show();
    }
}
