import socket
import json
import threading
import time
import client_Ultrasonic  # 초음파 감지 센서 모듈
import client_Servomotor  # 서보 모터 제어 모듈

# 서버에 대한 정보
servo_server_host = '0.0.0.0'  # 서보 모터 제어용 서버 IP 주소
servo_server_port = 8889  # 서보 모터 제어용 서버 포트 번호
ultrasonic_server_host = '192.168.43.26'  # 초음파 감지 센서용 서버 IP 주소
ultrasonic_server_port = 8888  # 초음파 감지 센서용 서버 포트 번호
motor_activate = '0'  # 초기 서보 모터 동작 상태
buffer_size = 1024  # 버퍼 사이즈

# 실제적으로 서보 모터를 작동시키는 스레드
def run_servo_thread(value):
    servo_thread = threading.Thread(target=run_servo_motor, args=(value,))
    servo_thread.start()

# 큐에서 메시지를 꺼내어 처리하는 함수
def process_message():
    global motor_activate
    print("Test01")  # 확인용 출력
    server_socket = None
    while True:
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.bind((servo_server_host, servo_server_port))  # 서버 소켓을 호스트와 포트에 바인딩
            print("대기중.......")
            server_socket.listen()  # 클라이언트의 접속을 대기
            print(f"서버가 {servo_server_port} 포트에서 실행 중입니다.")
            break
        except Exception as e:
            print(f"소켓 바인딩 실패: {e}")
            if server_socket:
                server_socket.close()
            time.sleep(1)  # 잠시 대기 후 재시도

    while True:
        try:
            conn, addr = server_socket.accept()  # 클라이언트의 접속을 수락
            print(f"{addr}가 연결되었습니다.")
            data = conn.recv(buffer_size)  # 클라이언트로부터 데이터를 수신
            if not data:
                break
            message = data.decode().strip()  # 받은 데이터를 문자열로 변환 및 공백 제거
            try:
                print(f"메시지 수신 완료: {message}")
                message_json = json.loads(message)
                if message_json['message_type'] == 'servo_motor':
                    value = message_json['value']
                    if value in ['15', '145'] and motor_activate != value:
                        motor_activate = value
                        run_servo_thread(motor_activate)  # 수신한 메시지로 서보 모터 스레드 실행
            except json.JSONDecodeError as e:
                print(f"JSON Decode Error: {e}")
            finally:
                conn.close()  # 클라이언트 연결을 닫음
        except Exception as e:
            print(f"서버 오류: {e}")

# 서보모터 동작 함수
def run_servo_motor(value):
    print("서보모터 모듈 실행 중...")
    client_Servomotor.run(value)  # 서보모터.py 파일의 run 함수 호출

# 초음파 센서 동작 함수
def run_ultrasonic_sensor():
    print("초음파 감지센서 모듈 실행 중...")
    client_Ultrasonic.run(ultrasonic_server_host, ultrasonic_server_port)  # 초음파 감지센서.py 파일의 run 함수 호출

def main():
    print("main 함수 시작")
    run_servo_thread("15")

    # 각각의 모듈을 실행할 스레드 생성
    ultrasonic_thread = threading.Thread(target=run_ultrasonic_sensor)
    process_thread = threading.Thread(target=process_message)

    try:
        # 초음파 센서 모듈 실행
        ultrasonic_thread.start()
        print("초음파 센서 스레드 시작됨")
        process_thread.start()
        print("메시지 처리 스레드 시작됨")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        # Ctrl+C를 눌러 프로그램을 종료할 때 각 스레드를 정리하고 종료
        print("프로그램을 종료합니다.")
        ultrasonic_thread.join()  # 초음파 센서 스레드 종료 대기
        process_thread.join()  # 메시지 처리 스레드 종료 대기
    except Exception as e:
        print(f"메인 함수 오류: {e}")

if __name__ == "__main__":
    main()
