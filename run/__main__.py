import sys

if len(sys.argv) < 2:
    print(
        f'[-] Only one commnad required which is in ("train", "inference", "interactive", "train_tokenizer)',
        file=sys.stderr,
    )
    exit(-1)

_, command, *arguments = sys.argv

if command == "train":
    from .train import main, parser
elif command == "train_vis":
    from .train_vis import main, parser
elif command == "train_sent1":
    from .train_sent1 import main, parser
elif command == "train_nopre":
    from .train_nopre import main, parser
elif command == "inference":
    from .inference import main, parser
elif command == "inference_ensemble":
    from .inference_ensemble import main, parser
else:
    print(f'[-] Please type command in ("train", "inference")', file=sys.stderr)
    exit(-1)

exit(main(parser.parse_args(arguments)))