# utils/irt.py
import numpy as np

class ThreeParameterLogisticModel:
    def estimate_difficulty(self, user_answers):
        """
        IRT orqali savol qiyinligini hisoblaydi (soddalashtirilgan).
        """
        correct_count = user_answers.filter(is_correct=True).count()
        total_count = user_answers.count()
        correct_rate = correct_count / total_count if total_count > 0 else 0.5
        # Oddiy formula: difficulty = -ln(correct_rate / (1 - correct_rate))
        try:
            difficulty = -math.log(correct_rate / (1 - correct_rate)) if 0 < correct_rate < 1 else 0.0
            return max(-3.0, min(3.0, difficulty))  # -3.0 dan 3.0 gacha cheklash
        except:
            return 0.0