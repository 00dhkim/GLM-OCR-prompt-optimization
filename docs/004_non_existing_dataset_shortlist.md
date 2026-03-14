# 현재 저장소에 없는 OCR 데이터셋 shortlist

작성일: 2026-03-14

기준:

- 현재 저장소에서 이미 쓰고 있는 `KORIE`, `CORD`는 제외
- 한국어 OCR 평가에 바로 도움이 되는 것만 남김
- `공개 접근성`, `라벨 품질`, `도메인 다양성`, `추가 구현 난이도`를 같이 봄

## 다운로드 상태

이번 턴에서 실제로 내려받은 공개셋:

- `AbdullahRian/Korean.OCR.Img.text.pair`
  - 저장 위치: `data/external/hf/korean-ocr-img-text-pair`
  - 저장 수량: 100장
  - manifest: `data/external/hf/korean-ocr-img-text-pair/train.jsonl`
  - 실험용 split: `data/manifests/korean-ocr-img-text-pair/dev.jsonl`, `data/manifests/korean-ocr-img-text-pair/val.jsonl`
- `HumynLabs/Korean_Receipts_Dataset`
  - 저장 위치: `data/external/hf/korean-receipts`
  - 저장 수량: 20장
- `HumynLabs/Korean_User_Manuals_Dataset`
  - 저장 위치: `data/external/hf/korean-user-manuals`
  - 저장 수량: 20장
- `HumynLabs/Korean_Price_Tags_Image_Dataset`
  - 저장 위치: `data/external/hf/korean-price-tags`
  - 저장 수량: 20장

다운로드하지 않은 것:

- AI Hub 데이터셋 전부
  - 이유: 로그인/신청 절차가 필요하고, 이 턴에서는 자동 다운로드 가능한 공개셋만 먼저 수집함

중요:

- `AbdullahRian/Korean.OCR.Img.text.pair`는 `이미지 + reference_text`가 같이 있어서 현재 저장소에서 바로 평가에 쓸 수 있다.
- 위 Hugging Face 3종은 현재 공개 API 기준으로 `이미지 파일`만 바로 수집 가능했고, `reference_text` 라벨은 같이 내려오지 않았다.
- 따라서 현재 저장소에서는 `정식 OCR 평가 manifest`로 바로 쓰기 어렵고, `smoke test용 이미지 풀` 또는 `수동 라벨링 후보`로 쓰는 것이 맞다.

## 바로 추가할 만한 것

### 0. AbdullahRian - Korean.OCR.Img.text.pair

- 추천도: `상`
- 링크: https://huggingface.co/datasets/AbdullahRian/Korean.OCR.Img.text.pair
- 왜 남겼나:
  - 공개 API에서 `image + text`가 같이 확인됨
  - 현재 저장소의 `prepare-hf-image-text` CLI로 즉시 manifest 생성 가능
  - 이번 턴에서 이미 100개 샘플 다운로드와 split 생성까지 완료함
- 이 프로젝트에서의 용도:
  - 한국어 line OCR 보조 평가셋
  - KORIE 외 일반 텍스트 인식 성능 비교
- 한계:
  - 긴 줄 단위 이미지가 많아 문서 페이지 OCR과는 성격이 다름
  - 전사 품질은 별도 spot check가 필요함

### 1. AI Hub - 다양한 형태의 한글 문자 OCR

- 추천도: `상`
- 링크: https://aihub.or.kr/aidata/33987
- 왜 남겼나:
  - 한국어 문자/단어 recognition 평가셋으로 가장 무난함
  - 인쇄체와 손글씨를 같이 포함해서 범용성이 높음
  - 현재 저장소의 `reference_text` 기반 CER 평가와 잘 맞음
- 이 프로젝트에서의 용도:
  - `recognition-only` 평가셋
  - 한글 오탈자, 초중종성 붕괴, 공백 오류 분석
- 추가 시 메모:
  - 문서 전체 OCR보다는 crop/word 단위 실험에 더 적합

### 2. AI Hub - 공공행정문서 OCR

- 추천도: `상`
- 링크: https://aihub.or.kr/aidata/30724
- 왜 남겼나:
  - 영수증 밖의 문서형 OCR 평가셋으로 가치가 큼
  - 수기, 타자체, 인쇄체 혼합이라 모델 약점이 잘 드러남
  - 실제 서비스형 문서 OCR 검증에 더 가깝다
- 이 프로젝트에서의 용도:
  - `document OCR` 평가셋
  - 페이지 OCR 또는 필드 OCR 일반화 검증
- 추가 시 메모:
  - manifest에 넣기 전에 `페이지 전체 text`로 볼지 `crop text`로 볼지 먼저 정해야 함

### 3. AI Hub - 다중언어 OCR

- 추천도: `중상`
- 링크: https://www.aihub.or.kr/aihubdata/data/view.do?aihubDataSe=data&currMenu=115&dataSetSn=71730&pageIndex=7&srchDetailCnd=DETAILCND001&srchOptnCnd=OPTNCND001&srchOrder=ORDER001&srchPagePer=20&topMenu=100
- 왜 남겼나:
  - 한글+영문 혼합 환경에서 robustness를 보기 좋음
  - 간판, 표지, 실물 촬영 텍스트처럼 실제 환경 난이도를 줄 수 있음
- 이 프로젝트에서의 용도:
  - `mixed-script robustness` 평가
  - 중국어/영문 혼입 같은 출력 불안정성 체크
- 추가 시 메모:
  - pure Korean 성능만 볼 때보다, 안정성 회귀 테스트용으로 더 적합

## 보조용으로만 쓸 만한 것

### 4. Hugging Face - Korean User Manuals Dataset

- 추천도: `중`
- 링크: https://huggingface.co/datasets/HumynLabs/Korean_User_Manuals_Dataset
- 왜 남겼나:
  - 바로 접근 가능해서 smoke test용으로 좋음
  - 문서형 인쇄 OCR의 sanity check에 쓸 수 있음
- 한계:
  - 20 rows 수준이라 벤치마크로는 부족

### 5. Hugging Face - Korean Price Tags Image Dataset

- 추천도: `중`
- 링크: https://huggingface.co/datasets/Kratos-AI/Korean_Price_Tags_Image_Dataset
- 왜 남겼나:
  - 한글+숫자 리테일 텍스트를 빠르게 체크 가능
  - 짧은 텍스트 OCR 오류를 보기 좋음
- 한계:
  - 짧은 텍스트 위주라 장문 문서 OCR 검증에는 약함

### 6. Hugging Face - Korean Handwritten Notes Dataset

- 추천도: `중하`
- 링크: https://huggingface.co/datasets/HumynLabs/Korean_Handwritten_Notes_Dataset
- 왜 남겼나:
  - 손글씨 OCR smoke test가 필요하면 가장 쉽게 붙일 수 있음
- 한계:
  - 9 rows라 평가셋으로 보기에는 너무 작음

### 7. Hugging Face - Korean Receipts Dataset

- 추천도: `중`
- 링크: https://huggingface.co/datasets/HumynLabs/Korean_Receipts_Dataset
- 왜 남겼나:
  - 영수증 도메인 이미지 샘플을 빠르게 확보할 수 있음
  - 현재 저장소의 KORIE 외 보조 이미지 풀로는 쓸 만함
- 한계:
  - 공개 API 기준 전사 라벨이 바로 노출되지 않아 CER 평가셋으로 바로 쓰기 어렵다

## 이번에는 제외한 것

### AI Hub - OCR 데이터(교육)

- 제외 이유:
  - 메인 목록 노출은 확인했지만 상세 페이지와 라벨 구조를 이번 턴에서 확정하지 못함

### AI Hub - OCR 데이터(금융 및 물류)

- 제외 이유:
  - 도메인 가치는 높지만 상세 포맷 검증 전에는 shortlist에 넣기 이르다

### 상용 구매형 데이터셋

- 제외 이유:
  - 바로 실험에 붙이기 어렵고 접근 비용이 큼

## 사용법

### 1. 지금처럼 공개 이미지 샘플만 받기

이 저장소에는 Hugging Face 이미지셋 샘플을 내려받는 CLI가 이미 있다.

```bash
uv run glm-ocr-opt collect-hf-images \
  --dataset-id HumynLabs/Korean_Receipts_Dataset \
  --output-dir data/external/hf/korean-receipts \
  --limit 20
```

같은 방식으로 아래도 받을 수 있다.

```bash
uv run glm-ocr-opt collect-hf-images \
  --dataset-id HumynLabs/Korean_User_Manuals_Dataset \
  --output-dir data/external/hf/korean-user-manuals \
  --limit 20

uv run glm-ocr-opt collect-hf-images \
  --dataset-id HumynLabs/Korean_Price_Tags_Image_Dataset \
  --output-dir data/external/hf/korean-price-tags \
  --limit 20
```

### 2. 바로 평가 가능한 공개셋 받기

현재 가장 바로 쓸 수 있는 공개셋은 아래다.

```bash
uv run glm-ocr-opt prepare-hf-image-text \
  --dataset-id 'AbdullahRian/Korean.OCR.Img.text.pair' \
  --output-dir data/external/hf/korean-ocr-img-text-pair \
  --split train \
  --config default \
  --count 100 \
  --batch-size 100 \
  --image-field jpg \
  --text-field txt \
  --sample-prefix koocr
```

실험용 split 생성:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run glm-ocr-opt prepare-split \
  --source-manifest data/external/hf/korean-ocr-img-text-pair/train.jsonl \
  --output-dir data/manifests/korean-ocr-img-text-pair \
  --dev-count 60 \
  --val-count 40 \
  --seed 42
```

### 3. 현재 프로젝트에서 바로 쓸 수 있는 방식

현재 manifest 포맷은 아래처럼 `reference_text`가 반드시 필요하다.

```json
{
  "id": "sample-001",
  "image_path": "data/images/sample-001.png",
  "reference_text": "..."
}
```

그래서 지금 받아둔 Hugging Face 3종은 아래 둘 중 하나로 써야 한다.

1. smoke test 이미지셋으로만 사용
2. 수동 또는 별도 OCR로 `reference_text`를 만든 뒤 JSONL manifest 생성

반면 `AbdullahRian/Korean.OCR.Img.text.pair`는 이미 `reference_text`가 있어서 바로 평가에 쓸 수 있다.

```bash
uv run glm-ocr-opt seed-eval \
  --manifest data/manifests/korean-ocr-img-text-pair/dev.jsonl \
  --output-dir runs/korean-ocr-img-text-pair-seed
```

### 4. 평가셋으로 바꾸려면

가장 현실적인 절차는 아래다.

1. `data/external/hf/...`의 이미지 중 일부를 샘플링
2. 사람이 정답 전사를 작성
3. `examples/sample_manifest.jsonl` 형식으로 manifest 생성
4. `uv run glm-ocr-opt seed-eval --manifest ...` 형태로 평가 실행

### 5. AI Hub 데이터를 붙일 때

AI Hub 후보들은 라벨 품질 면에서는 더 적합하다. 실제 평가셋을 더 키우려면 아래 순서가 낫다.

1. `AbdullahRian/Korean.OCR.Img.text.pair`
2. `다양한 형태의 한글 문자 OCR`
3. `공공행정문서 OCR`
4. `다중언어 OCR`

## 결론

실제로 추가할 순서는 아래가 가장 합리적이다.

1. `AbdullahRian/Korean.OCR.Img.text.pair`
2. `AI Hub - 다양한 형태의 한글 문자 OCR`
3. `AI Hub - 공공행정문서 OCR`
4. `AI Hub - 다중언어 OCR`

이 구성이면 현재 저장소의 `영수증 중심 평가`를 `한국어 line OCR`, `한글 문자 인식`, `실문서`, `혼합 스크립트`까지 확장할 수 있다.
