import os
import configparser
import speech_recognition as sr
from langchain_community.llms import LlamaCpp
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.chains import ConversationalRetrievalChain
from gtts import gTTS
import playsound

class Inferencer:
    def __init__(self):
        self.lmm_chain_model = self._init_llama2_recipes()

    def _init_llama2_recipes(self):
        # 모델 준비
        llama_model = LlamaCpp(model_path='./llama-3-Korean-Bllossom-8B-Q4_K_M.gguf')

        # PDF 파일 준비 (예시로 파일 경로만 설정)
        pdf_file = "./manual2.pdf"

        if not os.path.isfile(pdf_file):
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_file}")

        loader = PyPDFLoader(pdf_file)
        documents = loader.load()

        # PDF 파일 내용 분할 / 벡터화
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=20)
        all_splits = text_splitter.split_documents(documents)

        # HuggingFace에서 제공하는 embedding 모델 사용 (예시 모델)
        model_name = "sentence-transformers/all-mpnet-base-v2"
        model_kwargs = {"device": "cuda"}
        embeddings = HuggingFaceEmbeddings(model_name=model_name, model_kwargs=model_kwargs)

        # FAISS를 사용하여 벡터 검색 준비
        vectorstore = FAISS.from_documents(all_splits, embeddings)

        # ConversationalRetrievalChain 설정
        chain = ConversationalRetrievalChain.from_llm(llama_model, vectorstore.as_retriever(), return_source_documents=True)

        return chain

    def get_llama2_answer_from_audio(self):
        """마이크로부터 음성을 받아 llama2 recipe로 응답 생성"""
        r = sr.Recognizer()

        # 마이크로부터 음성 입력 받기
        with sr.Microphone() as source:
            print("마이크에서 음성을 입력하세요:")
            audio = r.listen(source)

        # 구글 Speech-to-Text API를 사용하여 음성을 텍스트로 변환
        try:
            question = r.recognize_google(audio, language='ko-KR')
            print(f"인식된 질문: {question}")

            # llama2 모델을 사용하여 답변 생성
            chat_history = []
            result = self.lmm_chain_model({"question": f'Q:{question}', "chat_history": chat_history})
            response = result['answer']
            response = response[:response.find('\n')]

            return response

        except sr.UnknownValueError:
            print("음성을 인식할 수 없습니다.")
            return ""
        except sr.RequestError as e:
            print(f"구글 음성 인식 API 요청에 실패했습니다: {e}")
            return ""

    def speak_response(self, text):
        """gtts를 사용하여 응답을 음성으로 말하기"""
        tts = gTTS(text=text, lang='ko')
        tts.save("response.mp3")
        playsound.playsound("response.mp3")
        os.remove("response.mp3")

if __name__ == "__main__":
    inferencer = Inferencer()
    response = inferencer.get_llama2_answer_from_audio()
    print(f"응답: {response}")
    inferencer.speak_response(response)
