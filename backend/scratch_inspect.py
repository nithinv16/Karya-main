import inspect
try:
    from emergentintegrations.llm.openai import OpenAISpeechToText
    print("Class source:")
    print(inspect.getsource(OpenAISpeechToText))
    print("Transcribe method signature:")
    print(inspect.signature(OpenAISpeechToText.transcribe))
except Exception as e:
    print("Error:", e)