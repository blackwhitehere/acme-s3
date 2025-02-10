import argparse
from acme_s3.s3bench import run_benchmark



def parse_args():
    parser = argparse.ArgumentParser(
        prog="as3", description="Efficient access to S3"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Add benchmark subcommand
    bench_parser = subparsers.add_parser("bench", help="Run S3 transfer benchmark")
    bench_parser.add_argument("--bucket", required=True, help="S3 bucket name")
    bench_parser.add_argument("--prefix", default="s3_benchmark", 
                            help="S3 prefix for benchmark files (default: s3_benchmark)")
    
    return parser.parse_args()


def main_logic(args):
    if args.command == "bench":
        run_benchmark(args.bucket, args.prefix)
    else:
        print("Please specify a command. Use --help for usage information.")


def main():
    args = parse_args()
    main_logic(args)


if __name__ == "__main__":
    main()