"""Rotating theme bank. Each entry is fed to the LLM as the video's core message.
Add your own — the more specific the angle, the less generic the script.
"""
import random
from datetime import date

THEMES = {
    "discipline": [
        "Why waking up at 4am is not about the time — it's about proving you can suffer on command.",
        "Motivation is for amateurs. Discipline is doing it when you hate every second.",
        "The pain you avoid today becomes the regret you carry for the rest of your life.",
        "Hard choices, easy life. Easy choices, hard life. There is no third option.",
        "Your standards dropped when no one was watching. That's why you are where you are.",
        "Discipline is choosing between what you want now and what you want most.",
        "You are not tired. You are undisciplined. There is a difference.",
        "The man who does not control his mornings does not control his life.",
    ],
    "stoicism": [
        "Marcus Aurelius was the most powerful man on earth. He still wrote reminders to himself to stay humble.",
        "You don't control what happens. You control the story you tell yourself about what happens.",
        "The obstacle is the way. The thing blocking you is the thing teaching you.",
        "Seneca said: we suffer more in imagination than in reality. Your fear is a fiction.",
        "Amor fati. Love your fate — even the parts that broke you. Especially those.",
        "You can lose money, status, friends. You cannot lose your character unless you let it go.",
        "The stoic does not feel less. He feels fully and chooses his response anyway.",
    ],
    "loneliness": [
        "Walking alone is not weakness. It is the price of having standards nobody else has.",
        "Monk mode is not a phase. It is the only way to rebuild a man broken by comfort.",
        "The friends you lost were never friends. They were companions in distraction.",
        "Silence is where you meet yourself. That's why you keep running from it.",
        "A man alone with his work is a man becoming dangerous. Comfort is the enemy.",
        "Loneliness is not the absence of people. It's the absence of people who see you.",
        "The path narrows. Most people fall off. You walk it anyway.",
    ],
    "anti_modern": [
        "Social media is a slot machine in your pocket. You wonder why you can't focus.",
        "Comfort is a slow poison. Your ancestors built empires; you can't build a habit.",
        "Every notification is a small betrayal of your future self.",
        "You were promised freedom. They sold you distraction. The cage looks like a screen.",
        "Stop optimizing. Start suffering with purpose. That's the only path back.",
        "Modern life removes every cost and then wonders why nothing has value.",
        "The algorithm wants you soft. Soft men scroll. Hard men build.",
    ],
}


def pick_theme() -> tuple[str, str]:
    """Pick a (category, theme) — deterministic per day to avoid repeats."""
    today_str = date.today().isoformat()
    seed = int(today_str.replace("-", ""))
    rng = random.Random(seed)
    cat = rng.choice(list(THEMES.keys()))
    theme = rng.choice(THEMES[cat])
    return cat, theme


if __name__ == "__main__":
    cat, theme = pick_theme()
    print(f"[{cat}] {theme}")
