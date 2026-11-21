"""Curated premium long-form scripts for @StickVerse.

Each topic is a self-contained video: 6 scenes (hook -> problem -> shift ->
core -> application -> resolution), ~550 words / ~3:10-3:20 at Edge-TTS -8%.
"Long but not boringly long" — every scene earns its place.

No LLM is used at runtime. Scripts are written here (the channel's IP) so the
pipeline is fully free and deterministic. The queue (premium/queue.py) picks
the next unpublished topic on each workflow run — video 1 publishes first.

clip_category drives Mixkit footage selection (premium/mixkit.py). Categories
must exist in premium.mixkit.CATEGORIES.
"""

# Resolution dimensions for the cinematic compose (1920x1080 horizontal long-form).
VIDEO_W, VIDEO_H = 1920, 1080
FPS = 30


TOPICS = [
    # ============================================================
    # VIDEO 1 — Stoicism (publishes FIRST)
    # ============================================================
    {
        "id": "stop-asking-easier-life",
        "category": "Stoicism",
        "title": "Stop Asking For An Easier Life (Stoic Motivation)",
        "hook_line": "Stop asking for an easier life.",
        "recurring_phrase": "Ask to be stronger.",
        "thumbnail_text": "STOP ASKING",
        "scenes": [
            {
                "narration": "You keep asking for an easier life. A lighter load. A softer path. Fewer obstacles, fewer enemies, fewer mornings that test you. But that prayer, if it were answered, would be the thing that ruins you. Because an easier life does not build a stronger person. It builds a quieter one, and quiet is not the same as strong. The Stoics understood this two thousand years ago, and they wrote it down so you would stop repeating the same mistake.",
                "clip_category": "mountains",
            },
            {
                "narration": "Look at what ease has already done. You have more comfort than any generation before you, and less resilience. You flinch at small delays. You avoid hard conversations. You quit when the work stops being fun. You have trained yourself, slowly, to expect life to bend, and when it doesn't, you call it unfair. That is not the world being cruel. That is you being soft, and calling your softness a standard. The easier life you want is the life that is already making you weak.",
                "clip_category": "city",
            },
            {
                "narration": "Epictetus was born a slave. He was beaten. He was lame. And he said: do not ask that things go your way, ask that you become equal to whatever happens. That is the only prayer worth saying. Because you cannot control the world, but you can make yourself someone the world cannot break. The load is not the problem. You are asking to carry less, when you should be asking to carry more, so that what used to crush you becomes the thing you simply walk with.",
                "clip_category": "sea",
            },
            {
                "narration": "Strength is not given. It is forced into existence by resistance. A muscle grows only against weight. A bone densifies only under impact. A mind sharpens only against problems it cannot look up. Marcus Aurelius reminded himself every morning: today I will meet the ungrateful, the arrogant, the deceitful, and none of them can harm me, because none of them can make me abandon my own character. That is the deal. Difficulty is not punishment. It is the only mechanism through which you become someone worth being.",
                "clip_category": "sky",
            },
            {
                "narration": "So stop bargaining with your days. Stop hoping the meeting gets cancelled, the run gets rained out, the person you fear calling does not pick up. Do the hard thing first, on purpose, before the soft part of you negotiates. Keep the cold shower. Send the message that scares you. Finish the work you started avoiding three weeks ago. Each one is small. Each one is a vote, a vote for the stronger version of you that is currently being built or currently being abandoned, depending on what you do next.",
                "clip_category": "road",
            },
            {
                "narration": "You will not get an easier life. Not because the universe is against you, but because an easier life would be the worst thing that could happen to you. It would leave you exactly as you are. So change the prayer. Stop asking for fewer problems and start asking for more capacity. Stop asking for the load to lighten and start asking for the back to strengthen. One day you will look back and realize the hard parts were not in the way. They were the way.",
                "clip_category": "mountains",
            },
        ],
        "description": (
            "You keep asking for an easier life. The Stoics answered that prayer "
            "two thousand years ago — and the answer is that an easier life is the "
            "worst thing that could happen to you.\n\n"
            "Epictetus, born a slave, beaten and lame, didn't ask for things to go "
            "his way. He asked to become equal to whatever happened. Marcus Aurelius "
            "reminded himself each morning that no ungrateful or deceitful person "
            "could make him abandon his own character.\n\n"
            "Difficulty isn't punishment. It's the only mechanism through which you "
            "become someone worth being. Stop asking for fewer problems. Start asking "
            "for more capacity. The hard parts weren't in the way. They were the way.\n\n"
            "Subscribe for weekly cinematic motivation. New episodes every Wednesday "
            "and Saturday.\n\n"
            "#stoicism #motivation #discipline #mindset #selfimprovement"
        ),
        "tags": ["stoicism", "motivation", "discipline", "marcus aurelius",
                 "epictetus", "self improvement", "mindset", "philosophy",
                 "mental toughness", "men"],
        "hashtags": ["stoicism", "motivation", "discipline", "mindset"],
    },

    # ============================================================
    # VIDEO 2 — Mindset
    # ============================================================
    {
        "id": "you-are-not-behind",
        "category": "Mindset",
        "title": "You Are Not Behind (Motivation For Anyone Who Feels Late)",
        "hook_line": "You are not behind.",
        "recurring_phrase": "You are exactly where your choices have put you.",
        "thumbnail_text": "NOT BEHIND",
        "scenes": [
            {
                "narration": "You are not behind. I know it feels like you are. The friend who bought the house. The classmate who got the promotion. The stranger online whose morning routine looks like a religion. They are ahead, and you are late, and the gap is widening every day you waste. That is the story you have been sold. It is also the story that is quietly making you miserable, because you are running a race nobody is timing, against people who are not even running against you.",
                "clip_category": "city",
            },
            {
                "narration": "Comparison is a thief, but it is worse than that, it is a liar. It takes someone's highlight, their best hour, their single visible win, and sets it next to your worst year, your doubts, your private failures, and calls that a fair comparison. Then it hands you the verdict: behind. You absorb it. You start rushing. You start choosing things not because you want them but because they prove you are keeping up. And slowly you trade the life you actually wanted for a life that just looks good next to someone else's.",
                "clip_category": "abstract",
            },
            {
                "narration": "Here is the thing nobody tells you about timelines: they are not shared. A tree that blooms in spring is not late because the snowdrop bloomed in February. It has a different nature, a different season, a different job to do. You are not a snowdrop. You are not whoever you are comparing yourself to. You are whatever you are, and you open when you open, and forcing a flower that is not ready produces nothing but a broken petal and a longer wait.",
                "clip_category": "nature",
            },
            {
                "narration": "The only race that matters is the one between who you are today and who you were last year. That is the only comparison that is not a lie, because it is the only one with the full picture. Were you more honest? Did you keep one hard promise? Did you learn one thing you did not know? Then you are not behind. You are moving, at the only speed that is real, which is your own. The people you envy have years you did not see and winters you will not have to survive.",
                "clip_category": "sky",
            },
            {
                "narration": "So stop checking the lane beside you. Close the app that makes you feel small. Pick the one thing you actually want, not the impressive thing, the true thing, and put one hour into it today. Then another tomorrow. Speed does not matter here. Direction does. The person who walks toward the right thing for ten years arrives somewhere worth being. The person who sprints toward the wrong thing arrives tired, famous in the wrong rooms, and empty.",
                "clip_category": "road",
            },
            {
                "narration": "You are not behind. You are exactly where your choices have put you, and that is the most hopeful sentence you will hear today, because if your choices put you here, your choices can move you forward. Not to catch up to anyone. To catch up to yourself. To the version of you that already exists in potential, waiting to be built by steady, unglamorous, unseen work. Stop running their race. Start walking yours. You are not late. You are just beginning, for real this time.",
                "clip_category": "sea",
            },
        ],
        "description": (
            "You are not behind. Comparison is a liar — it sets someone's best hour "
            "next to your worst year and calls it a fair race.\n\n"
            "The only comparison that isn't a lie is the one with the full picture: "
            "who you are today versus who you were last year. The people you envy "
            "have years you didn't see and winters you won't have to survive.\n\n"
            "Your timeline isn't shared. You open when you open. Pick the one true "
            "thing and walk toward it — direction matters more than speed. You're "
            "not late. You're just beginning, for real this time.\n\n"
            "Subscribe for weekly cinematic motivation. New episodes every Wednesday "
            "and Saturday.\n\n"
            "#mindset #motivation #comparison #selfimprovement #discipline"
        ),
        "tags": ["mindset", "motivation", "comparison", "self improvement",
                 "discipline", "anxiety", "mental health", "purpose",
                 "personal growth", "stoicism"],
        "hashtags": ["mindset", "motivation", "selfimprovement", "discipline"],
    },

    # ============================================================
    # VIDEO 3 — Discipline
    # ============================================================
    {
        "id": "cost-of-who-you-almost-became",
        "category": "Discipline",
        "title": "The Cost Of Who You Almost Became (Motivation)",
        "hook_line": "There is a cost to who you almost became.",
        "recurring_phrase": "Every kept promise is a deposit.",
        "thumbnail_text": "ALMOST",
        "scenes": [
            {
                "narration": "There is a cost to who you almost became. Not the money you did not make. Not the job you did not get. The real cost is quieter, and it is paid every single day by a version of you that exists only as potential, the person you were going to be before the skipped mornings and the abandoned projects and the slow, comfortable drift into someone smaller. That person does not die loudly. They just stop showing up. And one day you realize you have not heard from them in years.",
                "clip_category": "road",
            },
            {
                "narration": "This is how it happens. Not one dramatic failure, but a thousand tiny surrenders. The alarm you silence. The chapter you do not write. The conversation you avoid. The run you skip because it is raining, and the next one because you are tired, and the next because skipping has stopped feeling like a decision and started feeling like a personality. None of them matter alone. All of them matter together. Each one is a vote, and you have been voting, for years, for someone you do not even like.",
                "clip_category": "city",
            },
            {
                "narration": "People talk about discipline like it is punishment. It is not. Discipline is loyalty to a future self, the only kind of love that actually compounds. When you do the hard thing now, you are not suffering. You are paying forward, into an account that matures into a person. And when you skip, you are not resting. You are withdrawing from that same account, and the interest is brutal. The person you almost became is not gone because they were impossible. They are gone because you stopped funding them.",
                "clip_category": "mountains",
            },
            {
                "narration": "Here is the uncomfortable math. You will become whoever you repeatedly act like. Not whoever you intend to be, not whoever you plan to be when life calms down, not whoever you would be if you had more time. Whoever you repeatedly act like. Act tired, you become tired. Act avoidant, you become avoidant. Act like someone who finishes what they start, even badly, even late, and slowly, irreversibly, you become someone who finishes. Identity is not a declaration. It is an accumulation.",
                "clip_category": "abstract",
            },
            {
                "narration": "So reclaim the smallest promise first. Not the whole life overhaul. One alarm, kept. One workout, done. One page, written. One hard message, sent. That is it. Do it today, and let it be unimpressive, and do it again tomorrow. The version of you that almost disappeared will feel it immediately, like a pulse in a limb you had stopped believing in. They are still in there. They have been waiting. And they do not need a hero. They need you to stop voting against them.",
                "clip_category": "nature",
            },
            {
                "narration": "The cost of who you almost became is real, and you have been paying it. But the account is not closed. Every kept promise is a deposit. Every hard hour is a vote for the person you can still become, not the perfect version, the real one, the one who does the work even when no one is watching and no one is impressed. You will not get back the years you drifted. But you can stop drifting today. The person you almost became is still possible. Go and meet them.",
                "clip_category": "sky",
            },
        ],
        "description": (
            "There is a cost to who you almost became — and it's paid every day by "
            "the version of you that exists only as potential.\n\n"
            "It doesn't happen through one dramatic failure, but a thousand tiny "
            "surrenders. Each skipped morning is a vote, and for years you've been "
            "voting for someone you don't even like.\n\n"
            "But the account isn't closed. You will become whoever you repeatedly "
            "act like — so act like someone who finishes. Every kept promise is a "
            "deposit. The person you almost became is still possible. Go and meet "
            "them.\n\n"
            "Subscribe for weekly cinematic motivation. New episodes every Wednesday "
            "and Saturday.\n\n"
            "#discipline #motivation #selfimprovement #habits #mindset"
        ),
        "tags": ["discipline", "motivation", "self improvement", "habits",
                 "consistency", "potential", "mindset", "personal growth",
                 "future self", "stoicism"],
        "hashtags": ["discipline", "motivation", "selfimprovement", "habits"],
    },

    # ============================================================
    # VIDEO 4 — Discipline / Success
    # ============================================================
    {
        "id": "discipline-is-remembering",
        "category": "Discipline",
        "title": "Discipline Is Remembering What You Want (Not Motivation)",
        "hook_line": "Discipline is not motivation.",
        "recurring_phrase": "Discipline is remembering.",
        "thumbnail_text": "REMEMBER",
        "scenes": [
            {
                "narration": "Discipline is not motivation. Motivation is a feeling. It arrives, it peaks, it leaves you at six in the morning with a cold floor and a warm bed, and it loses. Every time. If you are waiting to feel like doing the hard thing, you will do it almost never, and you will spend the rest of your life wondering why the people who seem to feel less are getting further. They are not more motivated. They have just learned the one thing motivation never teaches you.",
                "clip_category": "city",
            },
            {
                "narration": "The trap is this: you want two things, and they are at war. You want the body, and you want the extra hour of sleep. You want the business, and you want the evening off. You want the calm mind, and you want the scroll. Both are real wants. Both are yours. But you keep letting the smaller, louder, closer want win, the one that is here right now, warm and easy and three feet away, and you keep sacrificing the bigger, quieter, further one, the one that actually matters.",
                "clip_category": "road",
            },
            {
                "narration": "Discipline is remembering. That is all it is. In the exact moment the bed is warmest, discipline is the act of reaching back through time and remembering the person who decided, last night, clear-headed and honest, that today you would get up. That person knew something the morning version of you has forgotten: that you want the body more than the sleep, the business more than the evening, the life more than the comfort. Discipline is choosing to listen to the clearer version of yourself.",
                "clip_category": "mountains",
            },
            {
                "narration": "This is why willpower fails and discipline does not. Willpower is a fight, in the moment, between two versions of you, and the tired version almost always wins, because it is the one holding the remote. Discipline removes the fight. You decide once, in advance, when you are strong, and then you do not renegotiate in the morning. The decision is already made. The only thing left to do is execute. And execution, with the argument already settled, is quietly, almost boringly, possible.",
                "clip_category": "sea",
            },
            {
                "narration": "So make the decisions tonight. Not the goals, the decisions. What time the alarm goes. What you do in the first hour. Whether the phone is in the other room. Write them down when you are clear, and tomorrow, when you are not, read them and obey them like they were given to you by someone wiser, because they were. You, at your best, giving instructions to you, at your worst. That is the whole system. Not heroic. Just consistent. And consistency, over enough mornings, becomes a different life.",
                "clip_category": "nature",
            },
            {
                "narration": "You will not always feel like it. That was never the requirement. The requirement is that you remember what you want, really want, the thing you would be proud to want, and that you let that remembering carry you past the smaller want that is screaming in your ear. Do that enough mornings, and the gap between who you are and who you decided to be closes, slowly, then suddenly. Discipline is not punishment. It is just remembering. And remembering, repeated, is how a life gets built.",
                "clip_category": "sky",
            },
        ],
        "description": (
            "Discipline is not motivation. Motivation is a feeling — it peaks and "
            "leaves you at 6am with a cold floor and a warm bed, and it loses. "
            "Every time.\n\n"
            "The people getting further aren't more motivated. They've learned that "
            "discipline is remembering: reaching back to the clearer version of "
            "yourself who decided last night, and letting that remembering carry you "
            "past the smaller, louder want screaming in your ear.\n\n"
            "Willpower is a fight you'll lose. Discipline removes the fight — decide "
            "once, in advance, then execute. Remembering, repeated, is how a life "
            "gets built.\n\n"
            "Subscribe for weekly cinematic motivation. New episodes every Wednesday "
            "and Saturday.\n\n"
            "#discipline #motivation #habits #selfimprovement #mindset"
        ),
        "tags": ["discipline", "motivation", "habits", "willpower",
                 "self improvement", "morning routine", "mindset", "consistency",
                 "success", "stoicism"],
        "hashtags": ["discipline", "motivation", "habits", "selfimprovement"],
    },

    # ============================================================
    # VIDEO 5 — Mindset (comfort zone / growth)
    # ============================================================
    {
        "id": "comfort-zone-is-a-prison",
        "category": "Mindset",
        "title": "Your Comfort Zone Is A Prison (Not A Refuge)",
        "hook_line": "Your comfort zone is not a refuge.",
        "recurring_phrase": "It is a cage you built and called home.",
        "thumbnail_text": "CAGE",
        "scenes": [
            {
                "narration": "Your comfort zone is not a refuge. It is the place you retreated to the first time something hurt, the job you did not apply for, the person you did not approach, the risk you did not take, and then you told yourself you were being sensible. You were not being sensible. You were being afraid, and you renamed your fear preferences, and you have been living inside that rename ever since. The walls are not visible. That is what makes them so effective. You simply stopped going anywhere that required you to stretch.",
                "clip_category": "mountains",
            },
            {
                "narration": "Look at what comfort has cost you. Not in drama, but in absence. The skills you never built because the learning curve was steep. The relationships that never started because the first message felt risky. The version of you that never showed up because the current version preferred the couch. None of these feel like losses because they are invisible. You cannot mourn a life you never tried to live. But if you sit quietly for one honest minute, you can feel the weight of it, the specific shape of everything comfort talked you out of.",
                "clip_category": "city",
            },
            {
                "narration": "Here is the biological truth nobody markets to you. Comfort and growth are not friends. They are opposites. A system that is never stressed does not adapt. A muscle that is never loaded does not grow. A mind that is never confronted with what it cannot yet do does not sharpen. Comfort is the state of not changing, and not changing is the slowest form of decline, because the world keeps moving while you stay exactly as you were, and one day you look up and the gap between you and your own life is enormous, and you do not even know when it opened.",
                "clip_category": "abstract",
            },
            {
                "narration": "The Stoics did not romanticize suffering, but they were clear about this. The person who avoids all difficulty avoids becoming anything at all. Seneca said we should seek discomfort on purpose, not because pain is good, but because a will that is never tested is a will that does not exist. You think you are protecting yourself by staying comfortable. You are preserving a version of yourself that has no proof it can handle anything. And a self with no proof is the most fragile self there is, because it has never been dropped, so it lives in terror of the floor.",
                "clip_category": "sky",
            },
            {
                "narration": "So leave one room of the cage today. Not the whole thing. One. Send the message you have been editing for a week. Take the cold shower. Speak in the meeting. Apply for the thing you are underqualified for, which is the only kind of thing worth applying for. It will feel wrong, and that feeling is not a stop sign. It is the sensation of the wall moving, which is the sensation of you growing. The discomfort is not the cost of change. The discomfort is the change. Without it, nothing happens, ever.",
                "clip_category": "road",
            },
            {
                "narration": "Your comfort zone was never protecting you. It was preserving you, like a jar preserves a specimen, still, unchanged, and not really alive. You do not have to burn your life down. You just have to stop treating comfort as the goal and start treating it as the occasional rest between efforts, which is all it was ever meant to be. Walk out of one room today. Then another tomorrow. The cage was always unlocked. The door was never the problem. You were. And that is the best news you will hear today, because it means you are also the way out.",
                "clip_category": "sea",
            },
        ],
        "description": (
            "Your comfort zone isn't a refuge — it's the cage you retreated to "
            "when something once hurt, and then renamed 'sensible.'\n\n"
            "Comfort and growth aren't friends; they're opposites. A system never "
            "stressed doesn't adapt. The Stoics didn't romanticize suffering, but "
            "Seneca was clear: a will never tested doesn't exist. You think you're "
            "protecting yourself — you're preserving a self with no proof it can "
            "handle anything.\n\n"
            "The discomfort isn't the cost of change. It IS the change. Leave one "
            "room of the cage today. The door was never locked.\n\n"
            "Subscribe for weekly cinematic motivation.\n\n"
            "#mindset #comfortzone #growth #selfimprovement #discipline"
        ),
        "tags": ["comfort zone", "mindset", "growth", "self improvement",
                 "discipline", "fear", "stoicism", "personal growth",
                 "discomfort", "potential"],
        "hashtags": ["mindset", "comfortzone", "growth", "selfimprovement"],
    },
]


def get_topic(topic_id: str) -> dict:
    """Return a topic by id (raises KeyError if not found)."""
    for t in TOPICS:
        if t["id"] == topic_id:
            return t
    raise KeyError(f"unknown topic id: {topic_id}")
