# GLM-OCR Prompt Optimization

GLM-OCR의 프롬프트를 바꿔가며 한국어 OCR 성능을 측정하고, 더 나은 프롬프트를 찾는 실험 저장소다.  
핵심은 `이미지 + 정답 전사(reference_text)`가 있는 평가용 manifest를 만들고, seed prompt 비교, 후보 프롬프트 생성, validation까지 같은 형식으로 반복 실행하는 것이다.

## 1. 이 프로젝트가 하는 일

이 시스템은 크게 5단계로 움직인다.

1. 데이터셋을 manifest 형식으로 준비한다.
2. 여러 seed prompt를 같은 데이터로 평가해 시작점을 고른다.
3. 실패 사례를 바탕으로 새 프롬프트 후보를 생성한다.
4. 후보들을 다시 같은 dev 세트에서 평가해 다음 라운드 winner를 고른다.
5. 최종 프롬프트를 별도 validation 세트에서 baseline과 비교해 채택 여부를 결정한다.

즉, 이 프로젝트는 단순 OCR 추론기가 아니라, `프롬프트 실험을 재현 가능하게 관리하는 실험 러너`에 가깝다.

## 2. 전체 시스템 구성

### 2.1 모듈 구조

- `src/glm_ocr_prompt_optimization/cli.py`
  - 전체 CLI 진입점이다.
  - dataset 준비, split 생성, seed 평가, optimize, validate, run-all 명령을 연결한다.
- `src/glm_ocr_prompt_optimization/dataset.py`
  - manifest 로드, KORIE manifest 생성, Hugging Face image-text manifest 생성, held-out benchmark split 생성을 담당한다.
- `src/glm_ocr_prompt_optimization/ocr_client.py`
  - 실제 OCR 모델 호출 계층이다.
  - 기본값은 Ollama 호환 OpenAI API 형태로 GLM-OCR를 호출한다.
  - 너무 긴 line image는 chunking해서 나눠 읽는다.
- `src/glm_ocr_prompt_optimization/metrics.py`
  - CER, normalized CER, token F1, 점수 계산, 중국어 혼입/반복 penalty를 계산한다.
- `src/glm_ocr_prompt_optimization/optimizer.py`
  - 실패 사례를 요약하고 OpenAI 모델로 새 프롬프트 후보를 생성한다.
- `src/glm_ocr_prompt_optimization/experiment.py`
  - seed 평가, optimize 라운드, validation, 최종 채택 판단을 실제로 실행한다.
- `src/glm_ocr_prompt_optimization/logger.py`
  - predictions, evaluations, aggregate CSV, prompt catalog를 파일로 남긴다.

### 2.2 실행 단계

실험은 보통 아래 흐름으로 진행된다.

1. `prepare-*` 계열 명령으로 manifest를 만든다.
2. `seed-eval`로 기본 프롬프트들(`P0`~`P3`)을 비교한다.
3. `optimize`로 failure analysis -> candidate generation -> 후보 재평가를 반복한다.
4. `validate`로 baseline prompt와 최종 prompt를 별도 validation 세트에서 비교한다.
5. 필요하면 `scripts/generate_*_report.py`로 차트 포함 보고서를 만든다.

`run-all`은 위 과정을 `seed -> optimize -> validation` 순서로 한 번에 묶어 실행하는 명령이다.

## 3. Manifest란 무엇인가

이 프로젝트에서 manifest는 `평가에 사용할 샘플 목록`이다.  
한 줄에 한 샘플씩 들어가는 JSONL 파일이며, 최소한 아래 정보가 필요하다.

```json
{
  "id": "sample-001",
  "image_path": "images/sample-001.png",
  "reference_text": "정답 전사",
  "split": "dev",
  "metadata": {
    "source": "korie"
  }
}
```

필드 의미:

- `id`: 샘플 식별자
- `image_path`: OCR에 넣을 이미지 경로
- `reference_text`: 정답 텍스트
- `split`: `dev`, `val`, `test` 같은 용도 표시
- `metadata`: 데이터 출처, 카테고리, HF split 같은 보조 정보

중요한 점은 이 프로젝트가 데이터셋 이름 자체를 기준으로 평가하지 않는다는 것이다.  
실험 대상은 항상 `어떤 manifest를 넘겼는지`로 결정된다.

즉:

- `data/manifests/korie-ocr/dev.jsonl`을 넘기면 KORIE 실험
- 여러 manifest를 합쳐 held-out split를 다시 만들면 새로운 benchmark 실험

## 4. 데이터셋은 어떻게 선택되는가

### 4.1 선택의 기준은 manifest 경로다

이 저장소는 `이번 실험에서 어떤 데이터셋을 쓸지`를 코드 내부 상수로 고정하지 않는다.  
사용자가 어떤 manifest를 준비하고, 어떤 경로를 `seed-eval`, `optimize`, `validate`, `run-all`에 넘기느냐가 곧 실험 대상 선택이다.

예를 들면:

- `uv run glm-ocr-opt seed-eval --manifest data/manifests/korie-ocr/dev.jsonl ...`
  - KORIE dev 세트 평가
- `uv run glm-ocr-opt run-all --dev-manifest ... --val-manifest ...`
  - dev/val manifest 쌍으로 한 번에 전체 실험
- `./scripts/run_manifest_experiment.sh ...`
  - 이미 준비된 dev/val manifest를 사용하는 실험
- `./scripts/run_hf_prepare_and_experiment.sh ...`
  - HF dataset에서 이미지를 받고 manifest를 만든 뒤 실험
- `./scripts/run_heldout_benchmark_experiment.sh ...`
  - 여러 manifest를 합쳐 filtered held-out benchmark를 만들고 실험

### 4.2 자주 쓰는 선택 방식

이 저장소에서 현재 실질적으로 쓰는 선택 방식은 세 가지다.

1. 이미 있는 `dev.jsonl`, `val.jsonl`로 바로 실행
2. Hugging Face 공개셋에서 `image + text`를 받아 manifest 생성 후 실행
3. 여러 source manifest를 합쳐 필터링하고 stratified held-out split를 다시 만들어 실행

### 4.3 held-out benchmark는 어떻게 제어되는가

`prepare-heldout-benchmark`는 여러 manifest를 합친 뒤 아래 조건으로 샘플을 걸러낸다.

- `max_text_length`
- `max_image_width`
- `max_aspect_ratio`

그 다음 텍스트 길이와 이미지 aspect ratio, source를 기준으로 bucket을 만들고, stratified 방식으로 `dev`와 `val`에 나눈다.  
즉 held-out benchmark는 단순 랜덤 분할이 아니라, 너무 긴 텍스트나 극단적으로 긴 이미지가 결과를 왜곡하지 않도록 제어된 split이다.

## 5. 현재 평가 대상이 되는 데이터셋들

### 5.1 바로 평가 가능한 데이터셋

아래 데이터셋들은 현재 코드와 manifest 구조에 바로 맞는다.

#### KORIE

- 성격: 한국어 영수증 OCR
- 준비 방식: `prepare-korie-ocr`
- 특징:
  - 영수증 도메인이라 현재 프로젝트의 출발점과 가장 잘 맞는다.
  - 이미지와 정답 텍스트가 있어 OCR recognition 평가가 쉽다.
  - 실제 영수증 노이즈가 있어 프롬프트 차이가 드러나기 좋다.

#### CORD-v2

- 성격: 영수증 문서 OCR
- 준비 방식: `prepare-cord-v2`
- 특징:
  - Hugging Face에서 ground truth를 받아 줄 단위 텍스트로 재구성한다.
  - 한국어 전용은 아니지만 receipt OCR 비교 기준으로 유용하다.
  - line ordering을 다시 맞춰 text로 펴는 전처리가 포함된다.

### 5.2 이미지 샘플 확보용 데이터셋

아래 데이터셋들은 현재 저장소에서 `collect-hf-images`로 이미지를 받기는 쉽지만, `reference_text`가 바로 없어서 정식 평가 manifest로는 바로 쓰기 어렵다.

#### `HumynLabs/Korean_Receipts_Dataset`

- 성격: 한국어 영수증 이미지 샘플
- 용도:
  - smoke test
  - 수동 라벨링 후보
- 한계:
  - 현재 파이프라인에서 바로 CER 평가용 manifest로 쓰기 어렵다.

#### `HumynLabs/Korean_User_Manuals_Dataset`

- 성격: 한국어 매뉴얼/문서 이미지
- 용도:
  - 문서형 OCR sanity check
- 한계:
  - 규모가 작고 라벨 연결이 약하다.

#### `Kratos-AI/Korean_Price_Tags_Image_Dataset`

- 성격: 가격표/리테일 짧은 텍스트
- 용도:
  - 숫자와 짧은 한글 OCR smoke test
- 한계:
  - 장문 문서 OCR 대표셋으로는 약하다.

### 5.3 보고서에서 후보로 조사된 데이터셋

`docs/003_korean_ocr_dataset_survey.md`, `docs/004_non_existing_dataset_shortlist.md`에는 확장 후보가 정리되어 있다.

- AI Hub 다양한 형태의 한글 문자 OCR
  - 문자/단어 recognition 평가용
- AI Hub 공공행정문서 OCR
  - 문서 OCR 일반화 평가용
- AI Hub 다중언어 OCR
  - mixed-script robustness 평가용

이 데이터셋들은 현재 저장소에 즉시 연결된 상태는 아니지만, 향후 manifest만 맞추면 같은 파이프라인으로 평가할 수 있다.

### 5.4 제거한 데이터셋 메모

- `AbdullahRian/Korean.OCR.Img.text.pair`
  - 한때 `data/external/hf/korean-ocr-img-text-pair`에 다운로드해 시험적으로 사용했다.
  - 그러나 실제 샘플을 눈으로 검토한 결과, 의미 있는 OCR benchmark라기보다 LLM 생성 텍스트에 가까운 품질 문제를 확인했다.
  - 따라서 현재는 로컬 데이터와 README의 추천 목록에서 제거했다.
  - 과거 `runs/`와 `docs/`에 남아 있는 언급은 역사적 실험 기록일 뿐, 현재 사용 권장 대상이 아니다.

## 6. 각 데이터의 성격은 왜 중요한가

이 프로젝트는 데이터가 다르면 같은 프롬프트가 항상 이기지 않는다고 본다.  
예를 들어:

- 영수증 OCR은 짧은 항목명, 숫자, 특수문자, 줄 정렬이 중요하다.
- line OCR은 긴 가로 이미지, chunking, 반복 출력 억제가 더 중요하다.
- 문서 OCR은 긴 문장, 문단, 다양한 줄바꿈 안정성이 중요하다.
- mixed-script OCR은 한글이 한자로 오염되거나 영문이 섞이는 문제를 더 강하게 봐야 한다.

그래서 평가셋을 바꾸는 것은 단순히 입력 파일만 바꾸는 일이 아니라,  
`무엇을 좋은 OCR이라고 볼지`의 기준을 함께 바꾸는 일이다.

## 7. 프롬프트 최적화는 어떤 원리로 작동하는가

### 7.1 시작점: seed prompt 비교

먼저 `prompts.py`의 기본 프롬프트들을 같은 dev 세트에서 비교한다.

- `P0`: 거의 빈 baseline
- `P1`: 정확히 보이는 텍스트를 전사하라는 짧은 규칙
- `P2`: 번역/수정/추측 금지 추가
- `P3`: reading order, line break, 반복 억제까지 더한 버전

여기서 가장 점수가 높은 프롬프트가 optimizer의 시작점이 된다.

### 7.2 실패 사례 분석

`optimizer.py`는 현재 프롬프트의 aggregate metric과 실패 샘플들을 OpenAI 모델에 넘겨서 먼저 실패 원인을 요약한다.

요청하는 분석은 대략 아래 성격이다.

- 어떤 오류가 반복되는가
- 현재 프롬프트에서 무엇은 유지해야 하는가
- 다음 후보에서는 어떤 패턴을 피해야 하는가
- 더 나은 rewrite 전략은 무엇인가

즉, 바로 후보를 뽑기 전에 먼저 `왜 실패했는지`를 구조화한다.

### 7.3 후보 프롬프트 생성

그 다음 같은 실패 사례와 분석 결과를 바탕으로 새 후보 프롬프트 여러 개를 생성한다.  
이때 시스템은 대체로 아래 규칙을 선호한다.

- English-first
- 짧고 명령형 문장
- visible text only
- plain text only
- 번역, 보정, 추측 금지
- 한국어를 중국어 한자로 치환하지 말 것
- line break와 reading order 유지
- 반복 출력 금지
- `[unclear]` 같은 placeholder 남발 금지

### 7.4 후보 재평가와 winner 선택

생성된 후보들을 다시 같은 dev manifest에서 전부 평가한다.  
가장 높은 `mean_total_score`를 얻은 프롬프트가 해당 라운드 winner가 된다.  
동점이면 더 짧은 프롬프트를 우선한다.

### 7.5 최종 채택 판단

validation에서는 아래 순서로 최종 채택을 판단한다.

`experiment.py`의 규칙은 대체로 아래와 같다.

- optimized prompt 길이가 `1024`자를 넘으면 탈락
- `mean_cer`가 baseline보다 낮으면 optimized 채택
- `mean_total_score` 차이가 `0.01` 이하로 사실상 비기면 더 짧은 프롬프트 채택
- 그 외에는 baseline 유지

즉, optimize 라운드 winner는 `mean_total_score` 중심으로 뽑고, 최종 채택은 validation `mean_cer`를 우선한다.

## 8. 평가는 어떤 지표로 이루어지는가

`metrics.py` 기준으로 주요 지표는 아래와 같다.

- `raw CER`
  - 원문 기준 문자 오류율
- `normalized CER`
  - 공백/줄바꿈 정규화 후 문자 오류율
- `token F1`
  - 토큰 단위 겹침 정도
- `base_score`
  - 기본 점수
- `penalties`
  - 비정상 출력에 대한 감점

기본 모드에서 점수는 아래 식으로 계산한다.

- `base_score = 0.85 * (1 - cer) + 0.15 * token_f1`
- `total_score = base_score - penalties.total`

현재 penalty는 아래 둘만 본다.

- Chinese contamination
  - 한국어 문서인데 예측에 중국어 한자가 과하게 섞이는 현상
- repetition
  - 반복 n-gram, 이상한 문자 반복

AI Hub 공공행정문서 OCR처럼 `evaluation_mode=unordered_characters`가 붙은 데이터셋은 공백과 reading order를 평가에서 제외한다.
이 모드에서는:

- 공백 제거 후 문자 멀티셋 기준으로 비교한다.
- `raw_cer`, `cer`는 순서 무시 문자 기준 CER로 계산한다.
- `token_f1`은 문자 멀티셋 F1로 계산한다.

보고서에서는 `mean_total_score`뿐 아니라 `mean_cer`, `mean_token_f1`, penalty rate를 함께 봐야 한다.

## 9. 출력물은 어떻게 쌓이는가

실험 결과는 보통 `runs/<run-name>/` 아래에 저장된다.

대표 구조:

```text
runs/<run-name>/
  seed/
    seed_aggregate.csv
    best_seed_prompt.txt
    P0/
    P1/
    ...
  optimize/
    optimization_aggregate.csv
    all_candidates.jsonl
    final_prompt.txt
    round_01/
    round_02/
    ...
  validation/
    validation_aggregate.csv
    baseline/
    final/
  adopted_prompt.txt
  final_report.json
```

각 프롬프트별 디렉터리에는 보통 아래가 들어간다.

- `predictions.jsonl`
- `evaluations.jsonl`

즉, 최종 점수만 남는 것이 아니라, 샘플별 예측과 평가 근거까지 추적할 수 있다.

## 10. 자주 쓰는 실행 방법

### 10.1 설치

```bash
uv sync
uv run glm-ocr-opt --help
```

### 10.2 KORIE manifest 준비

```bash
uv run glm-ocr-opt prepare-korie-ocr \
  --train-dir data/korie-ocr/train/train \
  --val-dir data/korie-ocr/val/val \
  --test-dir data/korie-ocr/test/test \
  --output-dir data/manifests/korie-ocr
```

### 10.3 기존 manifest로 전체 실험

```bash
./scripts/run_manifest_experiment.sh my-run \
  data/manifests/korie-ocr/dev.jsonl \
  data/manifests/korie-ocr/val.jsonl
```

실제 실행 없이 계획만 보려면:

```bash
./scripts/run_manifest_experiment.sh --dry-run my-run \
  data/manifests/korie-ocr/dev.jsonl \
  data/manifests/korie-ocr/val.jsonl
```

### 10.4 held-out benchmark 생성 후 전체 실험

```bash
./scripts/run_heldout_benchmark_experiment.sh \
  my-heldout-benchmark \
  data/manifests/korie-ocr/dev.jsonl \
  data/manifests/korie-ocr/val.jsonl
```

## 11. 환경 변수와 외부 의존성

기본적으로 두 모델 계층이 있다.

- OCR 실행 모델
  - 기본: Ollama 호환 GLM-OCR
- 프롬프트 후보 생성 모델
  - 기본: OpenAI Responses API

주요 환경 변수:

- `OLLAMA_BASE_URL`
- `OLLAMA_API_KEY`
- `OLLAMA_MODEL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `PHOENIX_API_KEY`
- `PHOENIX_COLLECTOR_ENDPOINT`
- `PHOENIX_BASE_URL`
- `PHOENIX_PROJECT_NAME`
- `PHOENIX_CLIENT_HEADERS`
- `OUTPUT_ROOT`

기본값은 `src/glm_ocr_prompt_optimization/config.py`에 정의되어 있다.

실전 연결 기준 권장 조합:

- OCR 서버
  - vLLM 같은 OpenAI 호환 서버를 쓰면 `OLLAMA_BASE_URL=http://localhost:8000/v1`처럼 맞춘다.
- Prompt optimizer
  - `OPENAI_API_KEY`가 필요하다.
- Arize AX
  - tracing은 `ARIZE_API_KEY` + `ARIZE_SPACE_ID` 또는 `PHOENIX_API_KEY`로 동작한다.
  - `PHOENIX_COLLECTOR_ENDPOINT`는 커스텀 OTLP collector가 있을 때만 넣는다.
  - Arize AX 기본 경로를 쓸 때는 비워두고 `arize-otel` 기본 endpoint를 사용한다.
  - `PHOENIX_BASE_URL`은 Phoenix prompt/dataset experiment API를 직접 쓸 때만 필요하다.
  - 예전 `ARIZE_API_KEY`, `ARIZE_SPACE_ID`도 읽지만 내부적으로 `PHOENIX_*`로 브리지된다.

`.env.example`에는 vLLM + Arize AX 조합의 기준값을 적어두었다.

## 12. 어떤 경우에 어떤 데이터를 쓰면 좋은가

- 영수증 OCR 프롬프트를 보고 싶다
  - KORIE, CORD-v2
- 문서 OCR 일반화 성능을 보고 싶다
  - AI Hub 공공행정문서 OCR 같은 문서형 셋을 manifest로 붙이는 방향
- mixed-script 안정성을 보고 싶다
  - AI Hub 다중언어 OCR 같은 셋을 별도 benchmark로 붙이는 방향

핵심은 “어떤 데이터셋이 더 좋으냐”보다 “이번에 무엇을 검증하려는가”에 맞춰 manifest를 고르는 것이다.

## 13. 이 프로젝트를 한 문장으로 요약하면

이 저장소는 `OCR 모델 자체를 바꾸지 않고`, `평가용 manifest와 반복 가능한 실험 러너를 이용해`, `더 안정적인 OCR 프롬프트를 찾는 시스템`이다.
