import random
import torch
from torch.nn import CrossEntropyLoss
from typing import Tuple, List, Dict
from itertools import islice
from pathlib import Path

from tokenizers import Tokenizer
from tokenizers.processors import TemplateProcessing

from babyberta import configs


loss_fct = CrossEntropyLoss()


def make_sequences(sentences: List[str],
                   num_sentences_per_input: int,
                   ) -> List[str]:

    gen = (bs for bs in sentences)

    # combine multiple sentences into 1 sequence
    res = []
    while True:
        sentences_in_sequence: List[str] = list(islice(gen, 0, num_sentences_per_input))
        if not sentences_in_sequence:
            break
        sequence = ' '.join(sentences_in_sequence)
        res.append(sequence)

    print(f'Num total sequences={len(res):,}', flush=True)
    return res


def split(data: List[str],
          seed: int = 2) -> Tuple[List[str],
                                  List[str],
                                  List[str]]:

    print(f'Splitting data into train/devel/test sets...')

    random.seed(seed)

    train = []
    devel = []
    test = []

    for i in data:
        if random.choices([True, False],
                          weights=[configs.Data.train_prob, 1 - configs.Data.train_prob])[0]:
            train.append(i)
        else:
            if random.choices([True, False], weights=[0.5, 0.5])[0]:
                devel.append(i)
            else:
                test.append(i)

    print(f'num train sequences={len(train):,}', flush=True)
    print(f'num devel sequences={len(devel):,}', flush=True)
    print(f'num test  sequences={len(test):,}' , flush=True)

    return train, devel, test


def forward_mlm(model,
                mask_matrix: torch.bool,  # mask_matrix is 2D bool array specifying which tokens to predict
                x: Dict[str, torch.tensor],
                y: torch.tensor,
                ) -> torch.tensor:
    output = model(**x)
    logits_3d = output['logits']
    logits_2d = logits_3d.view(-1, model.config.vocab_size)
    bool_1d = mask_matrix.view(-1)
    logits_for_masked_words = logits_2d[bool_1d]
    labels = y.view(-1).cuda()
    loss = loss_fct(logits_for_masked_words,  # [num masks in batch, vocab size]
                    labels)  # [num masks in batch]

    return loss


def load_tokenizer(config_path: Path,
                   max_num_tokens_in_sequence: int,
                   ) -> Tokenizer:

    tokenizer = Tokenizer.from_file(str(config_path))
    tokenizer.post_processor = TemplateProcessing(
        single="<s> $A </s>",
        pair=None,
        special_tokens=[("<s>", tokenizer.token_to_id("<s>")), ("</s>", tokenizer.token_to_id("</s>"))],
    )
    tokenizer.enable_padding(pad_id=tokenizer.token_to_id(configs.Data.pad_symbol), pad_token=configs.Data.pad_symbol)
    tokenizer.enable_truncation(max_length=max_num_tokens_in_sequence)
    return tokenizer


def load_wikipedia_sentences(input_filepath: Path,
                             percent: int,
                             shift: int,
                             ) -> List[str]:
    """
    return a sample of wiki sentences from a large text file, built using witokit.

    """

    if not 0 < percent < 100:
        raise Exception('Specified percent param should be in ]0, 100[')
    print('Sampling input file {}'.format(input_filepath))

    print('Counting number of lines in file...')
    with input_filepath.open('r', encoding='utf-8') as input_stream:
        num_lines = sum(1 for x in input_stream)
    print(f'Number of lines in {input_filepath}={num_lines:,}')
    final_count = num_lines * percent / 100
    sampling = num_lines / final_count

    # collect sentences
    res = []
    with open(input_filepath, 'r', encoding='utf-8') as input_stream:
        for idx, line in enumerate(input_stream):
            if (idx + shift) % round(sampling) == 0:  # TODO test that shift results in different corpora
                res.append(line.strip())

    return res
