"""Viral theme bank — controversial / clickbait angles engineered for retention.

Each theme is a contrarian or curiosity-gap hook that grabs attention in the
first 3 seconds. Organized by hook style so the LLM can match the title's
energy to the script's structure.

The themes are NOT generic motivation ("believe in yourself"). They are
specific, controversial, and impossible to scroll past:
  - "Why waking up at 5am is destroying you"
  - "Discipline is a scam sold to men who are already broken"
  - "The 3am rule that rewired my brain in 30 days"

Add your own — the more specific and contrarian, the better.
"""
import random
from datetime import date

THEMES = {
    # Controversial contrarian — flips a commonly-held belief
    "controversial": [
        "Waking up at 5am is destroying men who are already running on empty. Sleep debt is not discipline.",
        "Discipline is a scam sold to broken men. The real move is obsession — discipline is what losers call it.",
        "Reading self-help books is the new form of procrastination. You're addicted to the feeling of improving.",
        "Cold plunges are theatre. The men who actually change do boring painful things nobody films.",
        "Gratitude journals are coping mechanisms for men who refuse to fix the actual problem.",
        "Your morning routine is a superstition. Strip it away and you'd collapse by noon.",
        "Meditation is being sold to men who need to act, not sit. Stillness has become an excuse.",
        "Therapy culture has turned men into patients of their own lives. Stop pathologizing discipline.",
        "Networking is for men with nothing to offer. Build something and they will find you.",
        "Manifestation is the secular prayer of men who refuse to do the work.",
    ],
    # Brutal truth — strips away comfort, no softening
    "brutal_truth": [
        "You are not tired. You are weak. There is a difference and you know it.",
        "Nobody is coming to save you. Not your mother. Not your boss. Not god. Read that twice.",
        "The friends you lost were never friends. They were witnesses to your mediocrity.",
        "Your phone is a slot machine and you are the product. You wonder why you can't focus.",
        "You're not behind. You're exactly where your habits put you. That's the hard part.",
        "The woman you want does not want the man you are. Become the man or lose the woman.",
        "Your twenties are gone. Your thirties are deciding right now whether you deserve your forties.",
        "Comfort is the enemy. Every comfort you accept is a small betrayal of who you could have been.",
        "The pain you avoid today becomes the regret you carry for the rest of your life.",
        "You don't have a motivation problem. You have a lie you keep telling yourself problem.",
    ],
    # Curiosity gap — names a specific rule / concept the viewer doesn't know
    "curiosity_gap": [
        "The 3am rule: what you do between 3am and 5am decides the next ten years of your life.",
        "Marcus Aurelius wrote one line every morning that rewired how he ruled an empire.",
        "The two-hour rule that 0.1% of men actually use — and why it makes them uncatchable.",
        "There is a question Seneca asked himself every night. Most men die without ever asking it.",
        "The mirror test: the one exercise that separates men who change from men who talk.",
        "Goggins does one thing at 4am that no motivational speaker will ever tell you about.",
        "The stoics had a word for what you're feeling right now. It's not what you think it is.",
        "There is a 90-second window after fear hits where your entire future is decided.",
        "The empty chair technique that broke me out of a 3-year rut in a single night.",
        "Miyamoto Musashi wrote 21 rules. Rule number 9 is the one that ends soft men.",
    ],
    # Number + secret — listicle energy but brutal
    "number_secret": [
        "5 things disciplined men never do — and why every one of them is killing you slowly.",
        "The 3 habits that separate the top 1% of men from the 99% who will die average.",
        "7 things men do alone that quietly build empires — and you're doing none of them.",
        "The 1 decision at age 25 that decides whether you're rich or broken at 45.",
        "4 lies society told you about success that keep you poor, soft, and compliant.",
        "The 2-minute rule that turns weak men into dangerous ones in 30 days.",
        "6 things every man must do before 30 or spend 50 years paying for skipping them.",
        "The 5am test: 90% of men fail it. The 10% who pass run the world you live in.",
        "3 conversations every man must have with himself before he deserves anyone else's time.",
        "The 11th commandment nobody wrote down: thou shalt not die having built nothing.",
    ],
}


def pick_theme() -> tuple[str, str]:
    """Pick a (category, theme) — deterministic per day to avoid repeats.

    Uses the date as a seed so the same video isn't generated twice on the same
    day, but different days get different themes. With ~40 themes across 4
    categories, a Wed+Sat schedule (104 videos/year) will rarely repeat.
    """
    today_str = date.today().isoformat()
    seed = int(today_str.replace("-", ""))
    rng = random.Random(seed)
    cat = rng.choice(list(THEMES.keys()))
    theme = rng.choice(THEMES[cat])
    return cat, theme


if __name__ == "__main__":
    cat, theme = pick_theme()
    print(f"[{cat}] {theme}")
