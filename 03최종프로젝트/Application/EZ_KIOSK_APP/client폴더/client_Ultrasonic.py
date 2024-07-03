import socket
import time
import json
from gpiozero import DistanceSensor

def edit_json(message_type, value):
    data = {
        "message_type": message_type,
        "value": value
    }
    json_data = json.dumps(data)
    return json_data

def run(host, port):
    print("초음파 거리 측정기")

    # 초음파 센서 핀 번호 설정 (GPIO 핀 번호)
    TRIG01 = 23
    ECHO01 = 24

    TRIG02 = 17
    ECHO02 = 27

    # 초음파 센서 객체 생성
    sensor01 = DistanceSensor(echo=ECHO01, trigger=TRIG01)
    sensor02 = DistanceSensor(echo=ECHO02, trigger=TRIG02)

    # 파일을 서버로 전송하는 함수 정의
    def send_message(message_type, value, host, port):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client_socket.connect((host, port))
            message = edit_json(message_type, value)
            client_socket.sendall(message.encode())  # 메시지를 클라이언트로 전송
            print(f"메시지 전송 완료: {message}")
        except socket.error as e:
            print(f"소켓 에러: {e}")
        finally:
            client_socket.close()  # 명시적으로 소켓 닫기

    person_leave = 1

    try:
        detection_count = 0  # 거리 감지 결과 누적값 초기화
        while True:
            min_distance = 100
            for sensor in [sensor01, sensor02]:
                distance = sensor.distance * 100  # cm 단위로 변환
                if (min_distance > distance) and distance >= 5.0:
                    min_distance = distance
                print(f"Distance: {distance:.1f} cm")

            if 5.0 <= min_distance < 80.0:  # 감지 범위 내에 있는지 확인
                if (detection_count <= 4 and person_leave == 1 ) or (detection_count < 0):
                    detection_count += 1
                if detection_count >= 4 and person_leave == 1:  # 누적 값이 4 이상이면 메시지 전송
                    send_message("ultrasonic wave sensor", 'True', host, port)
                    person_leave = 0 
                    detection_count = 0  # 누적값 초기화
            else:
                if detection_count > -6:
                    detection_count -= 1
                if detection_count <= -5 and person_leave == 0: 
                    # 누적 값이 -5 이하이고, 사람이 있었던 경우 메시지 전송
                    send_message("ultrasonic wave sensor", 'False', host, port)
                    person_leave = 1 
                    detection_count = 0  # 누적값 초기화

            print(f"Min Distance: {min_distance:.1f} cm, Detection Count: {detection_count}")
            time.sleep(1)

    except KeyboardInterrupt:
        print("거리 측정 완료")
        sensor01.close()  # 센서 객체 닫기
        sensor02.close()  # 센서 객체 닫기

if __name__ == "__main__":
    run('192.168.43.38', 8889)
