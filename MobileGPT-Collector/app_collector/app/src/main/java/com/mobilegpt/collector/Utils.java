package com.mobilegpt.collector;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

// 유틸리티 함수들을 모아놓은 클래스
public class Utils {
    // "[x1,y1][x2,y2]" 형식의 문자열에서 좌표 값을 정수 배열로 추출하는 메서드
    public static int[] getBoundsInt(String stringBounds) {
        int[] bounds = new int[4]; // 좌표를 저장할 정수 배열
        // 괄호 안의 정수 값을 찾기 위한 정규식 패턴 정의
        Pattern pattern = Pattern.compile("\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]");
        Matcher matcher = pattern.matcher(stringBounds);

        // 정규식 패턴과 일치하는 경우
        if (matcher.matches()) {
            // 매칭된 그룹에서 정수 값을 추출하여 배열에 저장
            bounds[0] = Integer.parseInt(matcher.group(1)); // x1
            bounds[1] = Integer.parseInt(matcher.group(2)); // y1
            bounds[2] = Integer.parseInt(matcher.group(3)); // x2
            bounds[3] = Integer.parseInt(matcher.group(4)); // y2

        } else {
            // 일치하지 않는 경우 오류 메시지 출력
            System.out.println("잘못된 입력 형식입니다.");
        }
        return bounds;
    }
}
