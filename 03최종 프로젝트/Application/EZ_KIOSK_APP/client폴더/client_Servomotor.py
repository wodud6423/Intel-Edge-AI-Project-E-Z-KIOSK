from gpiozero import Servo
from time import sleep

def run(motor_degree):
    # 서보핀은 라즈베리파이 GPIO 12번 핀으로 설정
    servo_pin = 12

    # Servo 객체를 생성, min_pulse_width와 max_pulse_width는 서보 모터의 최소 및 최대 펄스 길이 설정
    servo = Servo(servo_pin, min_pulse_width=0.5/1000, max_pulse_width=2.5/1000)

    def set_servo_degree(degree):
        # 각도를 -1.0에서 1.0 사이의 값으로 변환하여 서보 모터를 제어
        normalized_degree = (degree - 90) / 90  # 0~180 각도를 -1.0~1.0 값으로 변환
        servo.value = normalized_degree  # 서보 모터에 변환된 각도 값을 설정
        return normalized_degree  # 변환된 각도 값을 반환

    try:
        # motor_degree 문자열을 정수형으로 변환
        degree = int(motor_degree)
        print(degree)
    except ValueError:
        print("Invalid motor degree value. It should be an integer.")
        return

    if 0 <= degree <= 180:
        normalized = set_servo_degree(degree)  # 입력받은 각도로 서보 모터를 움직임
        sleep(0.1)  # 0.1초 대기
        print(f"Degree : {degree} , Normalized : {normalized} ")  # 현재 각도와 정규화된 각도 출력
    else:
        print("Motor degree value out of range. It should be between 0 and 180.")

if __name__ == "__main__":
    run("180")  # 예시로 180도를 설정하여 실행
