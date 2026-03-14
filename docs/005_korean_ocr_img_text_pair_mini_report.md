# Korean OCR Img-Text Pair Mini Report

작성일: 2026-03-14

## 1. 왜 이 실험을 했는가

`AbdullahRian/Korean.OCR.Img.text.pair`는 한국어 이미지와 정답 텍스트가 같이 공개된 드문 데이터셋이다.  
현재 저장소에서 바로 CER 평가에 연결할 수 있어서, KORIE 외의 한국어 OCR 보조 평가셋으로 가치가 있다.

다만 실제 실행해 보니 샘플 1건 OCR에 약 50초가 걸렸다.  
그래서 이번에는 전체 `dev 60 / val 40` 실험 대신, 가장 짧은 line 이미지 위주 `dev 2 / val 2` mini benchmark로 먼저 경로를 검증했다.

## 2. 데이터 구성

| 항목 | 값 |
|---|---|
| 원본 데이터셋 | `AbdullahRian/Korean.OCR.Img.text.pair` |
| 원본 수집 수량 | 100 |
| mini dev | 2 |
| mini val | 2 |
| 선택 기준 | 이미지 면적이 작은 샘플 우선 |

이 표의 뜻:
- 긴 line 이미지가 많아서 전체 실험 비용이 매우 컸다.
- 그래서 먼저 짧은 샘플만 골라서 파이프라인이 끝까지 도는지 확인했다.

## 3. Seed 결과

| Prompt | Mean CER | Mean Total Score |
|---|---:|---:|
| `P0` | 0.5833 | 0.4167 |
| `P1` | 0.4167 | 0.5833 |
| `P2` | 0.4167 | 0.5833 |
| `P3` | 0.5833 | 0.4167 |

이 표의 뜻:
- mini dev에서는 `P1`, `P2`가 가장 좋았다.
- tie 상황에서는 코드상 더 짧은 프롬프트가 선택되므로 `P1`이 seed winner가 됐다.

선택된 seed prompt:

```text
Text Recognition:
보이는 글자를 한국어 중심으로 그대로 전사하라.
```

## 4. 1라운드 최적화 결과

최종 생성 프롬프트:

```text
Text Recognition: 보이는 글자를 한국어 표기로 그대로 옮기되, 비한국어 해석이나 의역 없이 문자 단위 전사에 집중한다.
```

이 문장의 뜻:
- optimizer는 “의역 금지”, “문자 단위 전사” 같은 제약을 더 강하게 넣는 방향으로 변형했다.

## 5. Mini Validation 결과

| Prompt | Mean CER | Mean Total Score | Non-Korean | Repetition | Empty |
|---|---:|---:|---:|---:|---:|
| baseline | 0.3409 | 0.6591 | 0.00% | 0.00% | 0.00% |
| optimized final | 0.3409 | 0.6591 | 0.00% | 0.00% | 0.00% |

이 표의 뜻:
- mini 검증셋 2건에서는 baseline과 optimized가 완전히 같은 결과를 냈다.
- 즉, 이 tiny run만 놓고 보면 “개선도 악화도 확인되지 않았다.”

## 6. 해석

이번 결과에서 확실히 말할 수 있는 것은 두 가지다.

1. 이 공개 데이터셋은 현재 파이프라인에 실제로 연결된다.
2. 하지만 현재 GLM-OCR 추론 속도 기준으로는 full split 반복 최적화가 너무 느리다.

따라서 다음 단계는 아래 둘 중 하나다.

1. 더 작은 평가셋을 여러 도메인으로 병렬 운영한다.
2. OCR 추론 속도를 개선한 뒤 `dev 60 / val 40` 실험으로 확장한다.
