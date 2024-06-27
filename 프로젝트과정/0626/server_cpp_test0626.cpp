#include <iostream>  // 표준 입출력 스트림 라이브러리
#include <stdexcept>  // 표준 예외 라이브러리
#include <thread>  // 멀티스레딩 라이브러리
#include <chrono>  // 시간 관련 라이브러리
#include <mutex>  // 뮤텍스 라이브러리
#include <condition_variable>  // 조건 변수 라이브러리
#include <queue>  // 큐 라이브러리
#include <string>  // 문자열 라이브러리
#include "json.hpp"  // JSON 처리 라이브러리

#ifdef _WIN32
    #include <winsock2.h>  // 윈도우 소켓 API 라이브러리
    #include <ws2tcpip.h>  // 윈도우 소켓 확장 라이브러리
    #define CLOSESOCKET closesocket  // 윈도우의 closesocket 함수를 CLOSESOCKET으로 정의
    #define popen _popen  // 윈도우의 _popen 함수를 popen으로 정의
    #define pclose _pclose  // 윈도우의 _pclose 함수를 pclose로 정의
    #pragma comment(lib, "Ws2_32.lib")  // 윈도우 소켓 라이브러리 링크
#else
    #include <sys/types.h>  // 시스템 데이터 타입 라이브러리
    #include <sys/socket.h>  // 소켓 라이브러리
    #include <netinet/in.h>  // 인터넷 주소 라이브러리
    #include <arpa/inet.h>  // IP 주소 변환 라이브러리
    #include <unistd.h>  // 유닉스 표준 함수 라이브러리
    #define SOCKET int  // 유닉스에서는 SOCKET을 int로 정의
    #define INVALID_SOCKET (-1)  // 유효하지 않은 소켓을 -1로 정의
    #define SOCKET_ERROR (-1)  // 소켓 오류를 -1로 정의
    #define CLOSESOCKET close  // 유닉스의 close 함수를 CLOSESOCKET으로 정의
#endif

#define PORT 65432  // 서버 포트 번호 정의
#define BUFFER_SIZE 1024  // 버퍼 크기 정의

using json = nlohmann::json;  // nlohmann::json을 json으로 간단히 사용

std::mutex mtx;  // 전역 뮤텍스 객체
std::condition_variable cv;  // 전역 조건 변수 객체
std::queue<std::string> message_queue;  // 전역 메시지 큐
bool stt_tts_active = false;  // bllossom_stt_tts.py 스레드 활성화 상태를 나타내는 플래그

// 오류 처리 함수
void handle_error(const std::string& msg) {
#ifdef _WIN32
    std::cerr << msg << ": " << WSAGetLastError() << std::endl;  // 윈도우에서 오류 메시지와 소켓 오류 코드 출력
#else
    perror(msg.c_str());  // 유닉스에서 오류 메시지 출력
#endif
    throw std::runtime_error(msg);  // 런타임 예외 발생
}

// 비디오 처리 함수
void video_processing() {
    std::string command = "python video_processing.py";  // 실행할 파이썬 스크립트 명령어
    std::cout << "Executing command: " << command << std::endl;  // 명령어 출력

    FILE* pipe = popen(command.c_str(), "r");  // 파이프 열기
    if (!pipe) {
        std::cerr << "Error executing Python script." << std::endl;  // 파이프 열기 실패 시 오류 메시지 출력
        return;  // 함수 종료
    }

    char buffer[128];  // 파이프에서 읽어올 버퍼
    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {  // 파이프에서 데이터 읽기
        std::string json_str(buffer);  // 버퍼 내용을 문자열로 변환
        try {
            // JSON 형식이 아닌 경우 예외 처리
            auto message = json::parse(json_str);
            std::lock_guard<std::mutex> lock(mtx);  // 뮤텍스 잠금
            message_queue.push(message.dump());  // 메시지 큐에 JSON 데이터 추가
            cv.notify_one();  // 조건 변수 알림
        } catch (const json::parse_error& e) {  // JSON 파싱 오류 발생 시
            // JSON 파싱 오류 무시
            std::cerr << "JSON parsing error: " << e.what() << " for data: " << json_str << std::endl;
        }
    }

    if (pclose(pipe) != 0) {  // 파이프 닫기
        std::cerr << "Error closing Python script execution." << std::endl;  // 파이프 닫기 실패 시 오류 메시지 출력
    }
}

// 클라이언트 처리 함수
void handle_client(SOCKET client_socket) {
    using namespace std::chrono;  // std::chrono 네임스페이스 사용

    char buffer[BUFFER_SIZE];  // 클라이언트로부터 데이터를 읽어올 버퍼
    const char* hello = "Hello from server";  // 클라이언트로 보낼 인사 메시지

    auto start = high_resolution_clock::now();  // 시작 시간 기록

    while (true) {
        memset(buffer, 0, BUFFER_SIZE);  // 버퍼 초기화

        int bytes_read = recv(client_socket, buffer, BUFFER_SIZE, 0);  // 클라이언트로부터 데이터 수신
        if (bytes_read == SOCKET_ERROR) {  // 수신 오류 발생 시
            handle_error("recv");  // 오류 처리 함수 호출
        } else if (bytes_read == 0) {  // 클라이언트 연결 종료 시
            std::cout << "Client disconnected" << std::endl;  // 클라이언트 연결 종료 메시지 출력
            CLOSESOCKET(client_socket);  // 소켓 닫기
            break;  // 루프 종료
        }

        std::string received_data(buffer, bytes_read);  // 수신한 데이터를 문자열로 변환
        try {
            json message = json::parse(received_data);  // 수신한 데이터를 JSON으로 파싱
            std::lock_guard<std::mutex> lock(mtx);  // 뮤텍스 잠금
            message_queue.push(message.dump());  // 메시지 큐에 JSON 데이터 추가
            cv.notify_one();  // 조건 변수 알림
        } catch (const json::parse_error& e) {  // JSON 파싱 오류 발생 시
            std::cerr << "JSON parsing error: " << e.what() << " for data: " << received_data << std::endl;
        }

        std::cout << "Message from client: " << buffer << std::endl;  // 클라이언트로부터 수신한 메시지 출력

        int bytes_sent = send(client_socket, hello, strlen(hello), 0);  // 클라이언트로 인사 메시지 전송
        if (bytes_sent == SOCKET_ERROR) {  // 전송 오류 발생 시
            handle_error("send");  // 오류 처리 함수 호출
        }
        std::cout << "Hello message sent" << std::endl;  // 인사 메시지 전송 완료 메시지 출력

        auto end = high_resolution_clock::now();  // 종료 시간 기록
        auto socket_duration = duration_cast<milliseconds>(end - start).count();  // 소켓 통신 시간 계산
        std::cout << "Socket communication duration: " << socket_duration << " ms" << std::endl;  // 소켓 통신 시간 출력
    }
}

// bllossom_stt_tts.py 실행 함수
void run_stt_tts() {
    std::string command = "python bllossom_stt_tts.py";  // 실행할 파이썬 스크립트 명령어
    std::cout << "Executing command: " << command << std::endl;  // 명령어 출력

    FILE* pipe = popen(command.c_str(), "r");  // 파이프 열기
    if (!pipe) {
        std::cerr << "Error executing Python script." << std::endl;  // 파이프 열기 실패 시 오류 메시지 출력
        return;  // 함수 종료
    }

    char buffer[128];  // 파이프에서 읽어올 버퍼
    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {  // 파이프에서 데이터 읽기
        std::cout << buffer;  // 스크립트 출력 내용을 콘솔에 출력
    }

    if (pclose(pipe) != 0) {  // 파이프 닫기
        std::cerr << "Error closing Python script execution." << std::endl;  // 파이프 닫기 실패 시 오류 메시지 출력
    }

    {
        std::lock_guard<std::mutex> lock(mtx);
        stt_tts_active = false;  // 스레드 실행 상태 변경
    }
    cv.notify_all();  // 모든 대기 스레드 깨우기
}

// 메시지 처리 함수
void process_messages(SOCKET client_socket) {
    std::thread video_thread;  // 비디오 처리 스레드를 저장할 변수

    while (true) {
        std::unique_lock<std::mutex> lock(mtx);
        cv.wait(lock, []{ return !message_queue.empty() || stt_tts_active; });

        if (stt_tts_active) {
            // bllossom_stt_tts.py 스레드가 활성화된 동안 다른 메시지 처리를 대기
            cv.wait(lock, []{ return !stt_tts_active; });
        }

        while (!message_queue.empty()) {
            std::string message = message_queue.front();
            message_queue.pop();
            lock.unlock();

            try {
                json msg = json::parse(message);
                std::string message_type = msg["message_type"];
                std::string value = msg["value"];

                std::cout << "Processed message: " << message << std::endl;

                // 특정 메시지 유형 처리
                if (message_type == "ultrasonic wave sensor" && value == "True") {
                    if (!video_thread.joinable()) {
                        video_thread = std::thread(video_processing);  // 비디오 처리 스레드 시작
                    }
                }

                // 기존 특정 메시지 유형 처리
                if (message_type == "client_classification" && value == "Wheelchair") {
                    json response = {
                        {"message_type", "servo_motor"},
                        {"value", "130"}
                    };  // 서보 모터 제어를 위한 응답 메시지 생성
                    std::string response_str = response.dump();  // 응답 메시지를 문자열로 변환

                    int bytes_sent = send(client_socket, response_str.c_str(), response_str.length(), 0);  // 클라이언트로 응답 메시지 전송
                    if (bytes_sent == SOCKET_ERROR) {  // 전송 오류 발생 시
                        handle_error("send");  // 오류 처리 함수 호출
                    }
                    std::cout << "Servo motor '130' message sent" << std::endl;  // 서보 모터 제어 메시지 전송 완료 메시지 출력
                } else if (message_type == "client_classification" && value == "Blind") {  // 메시지 유형이 "client_classification"이고 값이 "Blind"인 경우
                    std::cout << "Blind Check!!!!" << std::endl;
                    {
                        std::lock_guard<std::mutex> lock(mtx);
                        stt_tts_active = true;  // 스레드 실행 상태 설정
                    }
                    std::thread stt_tts_thread(run_stt_tts);  // bllossom_stt_tts.py 실행 스레드 생성
                    stt_tts_thread.detach();  // 스레드를 독립적으로 실행
                }

            } catch (const json::parse_error& e) {
                std::cerr << "JSON parsing error: " << e.what() << std::endl;
            }

            lock.lock();  // 다음 메시지 처리를 위해 뮤텍스 다시 잠금
        }
    }

    if (video_thread.joinable()) {
        video_thread.join();
    }
}

// 메인 함수
int main() {
#ifdef _WIN32
    WSADATA wsaData;  // WSA 데이터 구조체
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {  // 윈도우 소켓 초기화
        handle_error("WSAStartup failed");  // 초기화 실패 시 오류 처리
    }
#endif

    SOCKET server_fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);  // TCP 소켓 생성
    if (server_fd == INVALID_SOCKET) {  // 소켓 생성 실패 시
        handle_error("socket failed");  // 오류 처리 함수 호출
    }

    struct sockaddr_in address;  // 소켓 주소 구조체
    address.sin_family = AF_INET;  // 주소 체계 설정 (IPv4)
    address.sin_addr.s_addr = INADDR_ANY;  // 모든 인터페이스에서 수신
    address.sin_port = htons(PORT);  // 포트 번호 설정

    // 주소 재사용 옵션 설정
    int opt = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, (char *)&opt, sizeof(opt)) < 0) {
        handle_error("setsockopt failed");  // 옵션 설정 실패 시 오류 처리
    }

    if (bind(server_fd, (struct sockaddr*)&address, sizeof(address)) == SOCKET_ERROR) {  // 소켓과 주소 바인딩
        handle_error("bind failed");  // 바인딩 실패 시 오류 처리 함수 호출
    }

    if (listen(server_fd, 3) == SOCKET_ERROR) {  // 소켓을 수신 대기 상태로 설정
        handle_error("listen failed");  // 수신 대기 실패 시 오류 처리 함수 호출
    }

    while (true) {
        std::cout << "Waiting for a connection..." << std::endl;  // 연결 대기 메시지 출력

        SOCKET client_socket = accept(server_fd, nullptr, nullptr);  // 클라이언트 연결 수락
        if (client_socket == INVALID_SOCKET) {  // 연결 수락 실패 시
            handle_error("accept failed");  // 오류 처리 함수 호출
        }

        std::cout << "Connection accepted" << std::endl;  // 연결 수락 메시지 출력

        // 클라이언트 통신 처리를 위한 스레드 생성
        std::thread client_thread(handle_client, client_socket);
        client_thread.detach();  // 스레드를 독립적으로 실행

        // 메시지 처리를 위한 스레드 생성
        std::thread message_thread(process_messages, client_socket);
        message_thread.detach();  // 스레드를 독립적으로 실행
    }

    CLOSESOCKET(server_fd);  // 서버 소켓 닫기

#ifdef _WIN32
    WSACleanup();  // 윈도우 소켓 정리
#endif

    return 0;  // 프로그램 종료
}
