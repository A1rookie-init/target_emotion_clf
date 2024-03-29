
import argparse
import json
import logging
import os
import sys

import torch
import numpy as np
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    EvalPrediction
)
from datasets import Dataset
from sklearn.metrics import f1_score, roc_auc_score, accuracy_score

#kcelectra
from transformers import AdamW
from torch.optim.lr_scheduler import ExponentialLR
import re
import emoji
from soynlp.normalizer import repeat_normalize

# fmt: off
parser = argparse.ArgumentParser(prog="train", description="Train Table to Text with kcelectra")

g = parser.add_argument_group("Common Parameter")
g.add_argument("--output-dir", type=str, required=True, help="output directory path to save artifacts")
g.add_argument("--model-path", type=str, default="beomi/KcELECTRA-base-v2022", help="model file path")
parser.add_argument("--tokenizer", type=str, default="beomi/KcELECTRA-base-v2022", help="huggingface tokenizer path")

parser.add_argument("--max-seq-len", type=int, default=150, help="max sequence length")
g.add_argument("--batch-size", type=int, default=32, help="training batch size")
g.add_argument("--valid-batch-size", type=int, default=32, help="validation batch size")
g.add_argument("--accumulate-grad-batches", type=int, default=1, help=" the number of gradident accumulation steps")
g.add_argument("--epochs", type=int, default=10, help="the numnber of training epochs")
g.add_argument("--learning-rate", type=float, default=5e-6, help="max learning rate")
g.add_argument("--weight-decay", type=float, default=0.01, help="weight decay")
g.add_argument("--gpus", type=int, default=-1, help="the number of gpus")
g.add_argument("--seed", type=int, default=42, help="random seed")

os.environ["WANDB_DISABLED"] = "true"
# g = parser.add_argument_group("Wandb Options")
# g.add_argument("--wandb-run-name", type=str, default="kcbert_01", help="wanDB run name")
# g.add_argument("--wandb-entity", type=str, default="minkyung", help="wanDB entity name")
# g.add_argument("--wandb-project", type=str, default="korean_sa_clf", help="wanDB project name")
# fmt: on


def main(args):
    logger = logging.getLogger("train")
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))
        logger.addHandler(handler)
    os.makedirs(args.output_dir, exist_ok=True)
    logger.info(f'[+] Save output to "{args.output_dir}"')

    logger.info(" ====== Arguements ======")
    for k, v in vars(args).items():
        logger.info(f"{k:25}: {v}")

    logger.info(f"[+] Set Random Seed to {args.seed}")
    np.random.seed(args.seed)
    os.environ["PYTHONHASHSEED"] = str(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed(args.seed)  # type: ignore

    logger.info(f"[+] GPU: {args.gpus}")

    logger.info(f'[+] Load Tokenizer"')
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)

    logger.info(f'[+] Load Dataset')
    train_ds = Dataset.from_json("resource/data/nikluge-ea-2023-train.jsonl")
    valid_ds = Dataset.from_json("resource/data/nikluge-ea-2023-dev.jsonl")

    labels = list(train_ds["output"][0].keys())
    id2label = {idx:label for idx, label in enumerate(labels)}
    label2id = {label:idx for idx, label in enumerate(labels)}
    with open(os.path.join(args.output_dir, "label2id.json"), "w") as f:
        json.dump(label2id, f)

    def preprocess_data(examples):
        # take a batch of texts
        text1 = examples["input"]["form"]
        text2 = examples["input"]["target"]["form"]

        # cleansing
        emojis = ''.join(emoji.UNICODE_EMOJI.keys())
        pattern = re.compile(f'[^ .,?!/@$%~％·∼()\x00-\x7Fㄱ-힣{emojis}]+')
        url_pattern = re.compile(
            r'https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)')
        
        text1 = pattern.sub(' ', text1)
        text1 = url_pattern.sub('', text1)
        text1 = text1.strip()
        text1 = str(repeat_normalize(text1, num_repeats=2))

        if text2 is not None:
            text2 = pattern.sub(' ', text2)
            text2 = url_pattern.sub('', text2)
            text2 = text2.strip()
            text2 = str(repeat_normalize(text2, num_repeats=2))

        # encoding
        encoding = tokenizer(text1, text2, padding="max_length", truncation='only_first', max_length=args.max_seq_len)

        # add labels
        encoding["labels"] = [0.0] * len(labels)
        for key, idx in label2id.items():
            if examples["output"][key] == 'True':
                encoding["labels"][idx] = 1.0
        return encoding

    encoded_tds = train_ds.map(preprocess_data, remove_columns=train_ds.column_names)
    encoded_vds = valid_ds.map(preprocess_data, remove_columns=valid_ds.column_names)

    logger.info(f'[+] Load Model from "{args.model_path}"')
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_path,
        problem_type="multi_label_classification",
        num_labels=len(labels),
        id2label=id2label,
        label2id=label2id
    )

    args = TrainingArguments(
        output_dir=args.output_dir,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.valid_batch_size,
        num_train_epochs=args.epochs,
        weight_decay=args.weight_decay,
        load_best_model_at_end=True,
        metric_for_best_model= "f1",
        fp16="True", 
    )

    def multi_label_metrics(predictions, labels, threshold=0.5):
        sigmoid = torch.nn.Sigmoid()
        probs = sigmoid(torch.Tensor(predictions))
        y_pred = np.zeros(probs.shape)
        y_pred[np.where(probs >= threshold)] = 1
        y_true = labels
        f1_micro_average = f1_score(y_true=y_true, y_pred=y_pred, average='micro')
        roc_auc = roc_auc_score(y_true, y_pred, average = 'micro')
        accuracy = accuracy_score(y_true, y_pred)
        metrics = {'f1': f1_micro_average,
                   'roc_auc': roc_auc,
                   'accuracy': accuracy}
        return metrics

    def compute_metrics(p: EvalPrediction):
        preds = p.predictions[0] if isinstance(p.predictions, tuple) else p.predictions
        result = multi_label_metrics(predictions=preds, labels=p.label_ids)
        return result

    trainer = Trainer(
        model,
        args,
        train_dataset=encoded_tds,
        eval_dataset=encoded_vds,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics,
    )
    trainer.train()
    trainer.save_model(args.output_dir)


if __name__ == "__main__":
    exit(main(parser.parse_args()))

