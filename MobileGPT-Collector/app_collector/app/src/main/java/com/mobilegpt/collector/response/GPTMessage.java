package com.mobilegpt.collector.response;

import android.util.Log;

import org.json.JSONException;
import org.json.JSONObject;

// 서버로부터 받은 GPT의 응답 메시지를 파싱하고 관리하는 클래스
public class GPTMessage {
    private JSONObject action; // 수행할 전체 액션 JSON 객체
    private JSONObject args;   // 액션에 필요한 파라미터(인수) JSON 객체

    // 생성자: JSON 형식의 응답 문자열을 파싱합니다.
    public GPTMessage(String response_string) {
        try {
            Log.d("TAG", response_string);
            action = new JSONObject(response_string);
            // "parameters" 키에 해당하는 값을 파라미터로 가져옵니다.
            args = (JSONObject) action.get("parameters");
        } catch (JSONException e) {
            throw new RuntimeException(e);
        }
    }

    // 액션의 이름(예: "click", "input")을 반환합니다.
    public String getActionName() {
        try {
            // "name" 키에 해당하는 값을 액션 이름으로 가져옵니다.
            return (String) action.get("name");
        } catch (JSONException e) {
            throw new RuntimeException(e);
        }
    }

    // 액션에 필요한 파라미터(인수)를 담고 있는 JSONObject를 반환합니다.
    public JSONObject getArgs() {
        return args;
    }

}
