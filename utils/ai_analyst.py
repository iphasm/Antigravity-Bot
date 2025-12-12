
import os
import openai
from dotenv import load_dotenv

load_dotenv()

class QuantumAnalyst:
    def __init__(self):
        """Initializes the Quantum Analyst with OpenAI API."""
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = None
        
        if self.api_key:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
                print("🧠 Quantum Analyst: CONNECTED.")
            except Exception as e:
                print(f"❌ Quantum Analyst Error: {e}")
        else:
            print("⚠️ Quantum Analyst: No OPENAI_API_KEY found.")

    def analyze_signal(self, symbol, timeframe, indicators, personality="Standard"):
        """
        Generates a narrative analysis of the market situation.
        
        :param symbol: Ticker (e.g. BTCUSDT)
        :param timeframe: Timeframe (e.g. 15m)
        :param indicators: Dictionary of values (RSI, PRICE, BOLLINGER_GAP)
        :param personality: String name of the persona to adopt
        :return: String explanation from the AI.
        """
        if not self.client:
            return "⚠️ IA Desconectada. Configura OPENAI_API_KEY."

        # Construct the context
        prompt = f"""
        Act as a Professional Crypto Trader ({personality} Persona).
        Analyze this setup for {symbol} on {timeframe} timeframe:
        
        Price: {indicators.get('price', 'N/A')}
        RSI: {indicators.get('rsi', 'N/A')}
        Bollinger Gap: {indicators.get('gap', 'N/A')}%
        Recent Volume: {indicators.get('vol', 'Normal')}
        
        Task: Explain specifically WHY this is a good/bad entry or what the market is doing.
        Tone: {personality} (Sarcastic/Professional/Mystic depending on name).
        Length: MAX 2 SENTENCES. Concise.
        Language: Spanish.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a seasoned high-frequency trading algorithm with a personality."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"❌ Error de Análisis: {str(e)}"
