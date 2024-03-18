# target based emotion multi label classification 
텍스트 내 정보 중 target에 대해 느끼는 감정을 분류하는 모델 

## Directory Structue
```
resource
└── data

# Executable python script
run
├── infernece.py
└── train.py

# Python dependency file
requirements.txt
```

## Data Format
```
{
    "id": "nikluge-2023-ea-dev-000001",
    "input": {
        "form": "하,,,,내일 옥상다이브 하기 전에 표 구하길 기도해주세요",
        "target": {
            "form": "표",
            "begin": 20,
            "end": 21
        }
    },
    "output": {
        "joy": "False",
        "anticipation": "True",
        "trust": "False",
        "surprise": "False",
        "disgust": "False",
        "fear": "False",
        "anger": "False",
        "sadness": "False"
    }
}
```


## Enviroments
Install Python Dependency
```
pip install -r requirements.txt
```

## How to Run
### Train
```
python -m run train \
    --output-dir outputs/sa \
    --seed 42 --epoch 10 --gpus 2 \
    --learning-rate 2e-4 --weight-decay 0.01 \
    --batch-size=16 --valid-batch-size=16 \
    --wandb-project sa
```

### Inference
```
python -m run inference \
    --model-ckpt-path outputs/sa/<your-model-ckpt-path> \
    --output-path test_output.jsonl \
    --batch-size=64 \
    --device cuda:0
```
# 감정 분석 (2023) 
본 리포지토리는 2023 국립국어원 인공 지능 언어 능력 평가 중 감정 분석(Emotion Analysis) 경진대회에
참여하여 (f1-score%) 88.2를 기록. 

### Reference
국립국어원 모두의말뭉치 (https://corpus.korean.go.kr/)  
transformers (https://github.com/huggingface/transformers)  
KcELECTRA (https://github.com/Beomi/KcELECTRA)
