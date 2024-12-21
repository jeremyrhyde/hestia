from .speech_processor import SpeechProcessor

class SpeechToText(SpeechProcessor):
    def __init__(self, model_path):
        super().__init__()
        self.load_model(model_path)

    def recognize(self, audio):
        # Convert speech to text
        audio_data = self.preprocess(audio)
        # Recognize text using the model
        text = self.model.recognize(audio_data)
        return self.postprocess(text)