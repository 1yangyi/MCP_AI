# pip3 install transformers
# python3 deepseek_tokenizer.py
import transformers

chat_tokenizer_dir = "./"
def get_tokenizer(str):
        tokenizer = transformers.AutoTokenizer.from_pretrained( 
                chat_tokenizer_dir, trust_remote_code=True
                )
        tokens = tokenizer.encode(str)
        count = len(tokens)
        return tokens
