import json
import torch
from transformers import AutoTokenizer, AutoModel, StoppingCriteria, StoppingCriteriaList
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from transformers import pipeline
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
import time
import pexpect

# TOKENIZERS_PARALLELISM 환경 변수 설정
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# 임베딩 모델 로드
embedding_model_id = "sentence-transformers/all-mpnet-base-v2"
embedding_tokenizer = AutoTokenizer.from_pretrained(embedding_model_id)
embedding_model = AutoModel.from_pretrained(embedding_model_id)
embedding_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
embedding_model.to(embedding_device)

# 텍스트 생성 모델 로드
generation_model_id = "MLP-KTLim/llama-3-Korean-Bllossom-8B"
generation_pipeline = pipeline(
    "text-generation",
    model=generation_model_id,
    model_kwargs={"torch_dtype": torch.bfloat16},
    device_map="auto",
)
generation_pipeline.model.eval()

# 텍스트 임베딩 함수
def embed_text(text):
    inputs = embedding_tokenizer(text, return_tensors="pt", truncation=True, padding=True).to(embedding_device)
    with torch.no_grad():
        outputs = embedding_model(**inputs)
    return outputs.last_hidden_state.mean(dim=1).cpu().numpy()

# 임베딩 벡터와 질문/답변 저장
def create_embeddings(data):
    questions = [item['question'] for item in data]
    answers = [item['answer'] for item in data]
    question_embeddings = np.vstack([embed_text(question) for question in questions])
    return question_embeddings, answers

# 가장 유사한 질문 찾기
def find_most_similar(question, question_embeddings):
    question_embedding = embed_text(question)
    similarities = cosine_similarity(question_embedding, question_embeddings)
    most_similar_index = np.argmax(similarities)
    return most_similar_index

# 첫 문장이 나오면 중지하는 StoppingCriteria
class StopOnFirstPeriod(StoppingCriteria):
    def __init__(self, stop_token_id):
        self.stop_token_id = stop_token_id

    def __call__(self, input_ids, scores, **kwargs):
        for input_id in input_ids:
            if self.stop_token_id in input_id:
                return True
        return False

# 텍스트 생성 함수
def generate_answer_with_pipeline(question, answer, pipeline, max_length=512):
    input_text = f"Question: {question}\nAnswer: {answer}"
    inputs = pipeline.tokenizer(input_text, return_tensors="pt").to(pipeline.model.device)
    
    stop_token_id = pipeline.tokenizer.convert_tokens_to_ids(".")
    stopping_criteria = StoppingCriteriaList([StopOnFirstPeriod(stop_token_id)])

    outputs = pipeline.model.generate(
        **inputs,
        max_length=max_length,
        pad_token_id=pipeline.tokenizer.eos_token_id,
        stopping_criteria=stopping_criteria
    )
    
    generated_text = pipeline.tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # 'Answer:' 이후의 텍스트를 추출하고, 첫 번째 '.' 이후의 텍스트를 삭제
    answer_start = generated_text.find("Answer:") + len("Answer:")
    final_answer = generated_text[answer_start:].strip()
    
    # 첫 번째 '.' 이후의 텍스트를 삭제
    if '.' in final_answer:
        final_answer = final_answer[:final_answer.find('.') + 1]
    
    return final_answer

# 파일 시스템 이벤트 핸들러
class InputFileHandler(FileSystemEventHandler):
    def __init__(self, question_embeddings, answers):
        self.question_embeddings = question_embeddings
        self.answers = answers
        self.last_processed = time.time()

    def on_modified(self, event):
        if event.src_path.endswith("input.json"):
            # 파일 변경 후 5초 내에 발생한 추가 이벤트 무시
            if time.time() - self.last_processed < 5:
                return
            self.last_processed = time.time()
            print("input.json 파일이 변경되었습니다.")
            self.process_input_file()

    def process_input_file(self):
        # input.json 파일 로드
        with open("input.json", "r", encoding="utf-8") as f:
            input_data = json.load(f)
        
        if isinstance(input_data, dict) and "questions" in input_data:
            input_questions = [{'question': item['Q']} for item in input_data['questions']]
        else:
            print("input.json 형식이 올바르지 않습니다.")
            return
        
        # 질문에 대한 답변 생성
        responses = []
        for item in input_questions:
            question = item['question']
            most_similar_index = find_most_similar(question, self.question_embeddings)
            answer = self.answers[most_similar_index]
            final_answer = generate_answer_with_pipeline(question, answer, generation_pipeline)
            responses.append({'question': question, 'answer': final_answer})

        # 결과를 output.json 형식으로 저장
        with open("output.json", "w", encoding="utf-8") as f:
            json.dump(responses, f, ensure_ascii=False, indent=4)

        # output.json 파일을 원격 서버로 전송
        yj_dir = "scp output.json ubuntu@10.10.15.105:/home/ubuntu/EZ_KIOSK_FINAL_APP"
        yj_pass = "password:"
        yj_pwd = "ubuntu"
        child = pexpect.spawn(yj_dir)
        child.expect(yj_pass)
        child.sendline(yj_pwd)
        child.wait()

def main():
    # nolang.json 파일 로드 및 임베딩 생성
    with open("nolang.json", "r", encoding="utf-8") as f:
        nolang_data = json.load(f)
    
    if isinstance(nolang_data, list):
        question_embeddings, answers = create_embeddings(nolang_data)
    else:
        print("nolang.json 형식이 올바르지 않습니다.")
        return

    # 파일 시스템 이벤트 핸들러 설정
    event_handler = InputFileHandler(question_embeddings, answers)
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()
    print("파일 시스템 모니터링을 시작합니다.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()

