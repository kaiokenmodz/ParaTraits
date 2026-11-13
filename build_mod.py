"""Builds the ParaTraits content mod for Paralives.

Writes a mod folder whose Settings/*.setting files are *diffs* in the game's own manifest
format (the same format the in-game mod editor writes):
  @GUID  add an array element      gGUID  edit an existing element      =Field:value  set a field
Nothing from the base game is copied; traits, moodlets and rules are added on top of it.

Usage:  python build_mod.py <output_dir>
"""
import hashlib
import os
import sys

MOD_NAME = "ParaTraits - Sims-style Traits"
MOD_FOLDER = "ParaTraits"

# ------------------------------------------------------------------ game IDs (Early Access 0.1.9b)
LIFESTYLES_CATEGORY = 7431647724327720272
TRANSLATION_LIFESTYLES_TITLE = 967574391345791823   # "TraitCategory_Lifestyles"

EMO = dict(Happy=7613768505310365357, Sad=3906112767833573241, Stressed=6075452194107202843,
           Angry=4120972252083052140, Bored=4429253171760372756, Inspired=9101039463697177474,
           Disgusted=843198438205433365, Embarrassed=7928250651220520593, Amused=4808763899336838140,
           Flirty=4647454102258766267, Uncomfortable=3907213034891875060)
NEED = dict(Hunger=3390464559190696386, Sleep=4125638617189434272)
SKILL = dict(Cooking=3823409090312567399, Exercising=2496461569963932013, Piano=7943314533965034221,
             Guitar=5755067264783086685, Painting=7741760125396427716, Programming=8097812550914307014,
             Astronomy=2826202278347761056, Outdoorsiness=6339065498988541436)

ACTION = {
    "Eat": [4992821010057025513, 6738135351995789652],          # EatStandingEating, EatWhileSitting
    "Snack": ["EatingSnack", "EatingSnackBag", "EatIceCream", "EatSnackFromFridgeSequence"],
    "Cook": "CookGeneric", "TV": "Watch TV", "Music": "ListenToMusic",
    "Piano": ["PlayPiano", "PracticePiano"], "Guitar": ["PlayGuitar", "PracticeGuitar"],
    "Paint": ["PaintOnCanvas", "Paint"],
    "Exercise": ["Exercising_Crunch", "Exercising_PushUpOnYogaMat", "Exercising_Yoga",
                 "Exercising_BenchPressTrain", "JogOnTreadmill", "Jog", "Run"],
    "Computer": ["UseComputerFor2HoursProgramming", "UseComputerFor2HoursGraphicDesign", "PlayOnPhoneOneHourSequence"],
    "Telescope": "UseHobbyTelescope", "Nature": ["SmellFlowers", "WalkLeisurely"],
    "Romance": ["Kiss", "FirstKiss", "PassionateKiss", "Hug", "Slowdance"],
    "Chores": ["CleanItem", "CleanPlateActivity"],
}

# Idle autonomy rules by name (looked up in the game's Autonomy.setting).
RULES = [
    "Pastime_WatchTV", "Pastime_Daydream", "ReliefNeed_Cook", "ReliefNeed_EatSnack", "Reliefneed_EatFridgeLeftovers",
    "ReliefNeed_Nap", "SkillActivity_PracticePiano", "SkillActivity_PracticeGuitar", "SkillActivity_PlayPianoRandomSong",
    "SkillActivity_PlayGuitarRandomSong", "Pastime_ListenToMusic", "Social_DanceIfOthersDance", "SkillActivity_PaintOnEasel",
    "SkillActivity_FinishPaintingOnEasel", "Pastime_Draw", "SkillActivity_PracticeProgramming",
    "SkillActivity_PracticeGraphicDesign", "Pastime_PlayGameOnPhone", "Pastime_CheckSocialMedia", "Pastime_PlayAmongUs",
    "SkillActivity_UseTelescope", "Town_SmellFlowers", "Town_WalkLeisurely", "Pastime_DigGroundForFun",
    "SkillActivity_PushUpsOnYogaMat", "SkillActivity_UseThreadmill", "SkillActivity_UseBenchpress",
    "SkillActivity_PushUpOnFloor", "SkillActivity_DoYoga", "Exercise_FlexMuscle", "Social_TalkWith_CurrentHousehold",
    "Social_NPC_TalkWithFriendly", "Social_NPC_TalkWithFunny", "Emotion_KickSomethingAngrily", "Clean_DirtyItem",
    "Clean_Plates", "Clean_MopPuddle", "Clean_Fridge",
]
EXERCISE_RULES = ["SkillActivity_PushUpsOnYogaMat", "SkillActivity_UseThreadmill", "SkillActivity_UseBenchpress",
                  "SkillActivity_PushUpOnFloor", "SkillActivity_DoYoga", "Exercise_FlexMuscle"]
CHORE_RULES = ["Clean_DirtyItem", "Clean_Plates", "Clean_MopPuddle", "Clean_Fridge"]
SOCIAL_RULES = ["Social_TalkWith_CurrentHousehold", "Social_NPC_TalkWithFriendly", "Social_NPC_TalkWithFunny"]

# ------------------------------------------------------------------ the traits
# autonomy: {rule: score change}. react: (trigger, moodlet name, emotion, strength, minutes).
#   trigger is an ACTION key, "group" (while in a social group) or ("interval", minutes, chance).
# learn: skills learned faster.  drain: {need: extra decay per hour}.
TRAITS = [
    dict(id="Foodie", name="Foodie",
         desc="Loves good food. Cooks more often, savours every meal and picks up Cooking faster.",
         autonomy={"ReliefNeed_Cook": 3},
         react=[("Eat", "Savoured a meal", "Happy", 2, 180), ("Cook", "Kitchen magic", "Inspired", 1, 120)],
         learn=["Cooking"]),
    dict(id="Glutton", name="Glutton",
         desc="Always thinking about the next snack. Gets hungry faster and loves to eat.",
         autonomy={"ReliefNeed_EatSnack": 3, "Reliefneed_EatFridgeLeftovers": 3, "ReliefNeed_Cook": 1},
         react=[("Eat", "Full belly", "Happy", 1, 120), ("Snack", "Full belly", "Happy", 1, 120)], drain={"Hunger": 0.25}),
    dict(id="GymRat", name="Gym Rat",
         desc="Lives for a good workout. Exercises often, feels great afterwards and trains faster.",
         autonomy=dict({r: 4 for r in EXERCISE_RULES}, Pastime_WatchTV=-2),
         react=[("Exercise", "Post-workout high", "Happy", 2, 180)], learn=["Exercising"]),
    dict(id="CouchPotato", name="Couch Potato",
         desc="Happiest on the sofa. Watches lots of TV and finds exercise a real chore.",
         autonomy=dict({r: -3 for r in EXERCISE_RULES}, Pastime_WatchTV=4, Pastime_Daydream=2),
         react=[("TV", "Couch bliss", "Happy", 1, 120), ("Exercise", "Way too much effort", "Uncomfortable", 1, 120)]),
    dict(id="Lazy", name="Lazy",
         desc="Why stand when you can nap? Avoids chores and exercise, and tires out quicker.",
         autonomy=dict({r: -4 for r in CHORE_RULES}, **{r: -2 for r in EXERCISE_RULES}, ReliefNeed_Nap=4, Pastime_WatchTV=1),
         react=[("Chores", "Ugh, chores", "Uncomfortable", 1, 120)], drain={"Sleep": 0.1}),
    dict(id="MusicLover", name="Music Lover",
         desc="Music is life. Listens, plays and dances more, feels the music and learns Piano and Guitar faster.",
         autonomy={"Pastime_ListenToMusic": 4, "SkillActivity_PlayPianoRandomSong": 2, "SkillActivity_PlayGuitarRandomSong": 2,
                   "SkillActivity_PracticePiano": 1, "SkillActivity_PracticeGuitar": 1, "Social_DanceIfOthersDance": 2},
         react=[("Music", "Feeling the music", "Happy", 1, 120), ("Piano", "Feeling the music", "Happy", 1, 120),
                ("Guitar", "Feeling the music", "Happy", 1, 120)],
         learn=["Piano", "Guitar"]),
    dict(id="Artsy", name="Artsy",
         desc="Sees beauty everywhere. Paints and draws more, gets a creative spark from it and learns Painting faster.",
         autonomy={"SkillActivity_PaintOnEasel": 3, "SkillActivity_FinishPaintingOnEasel": 3, "Pastime_Draw": 2},
         react=[("Paint", "Creative spark", "Inspired", 2, 180)], learn=["Painting"]),
    dict(id="Techie", name="Techie",
         desc="Happiest behind a screen. Codes, designs and games more, gets in the zone and learns Programming faster.",
         autonomy={"SkillActivity_PracticeProgramming": 3, "SkillActivity_PracticeGraphicDesign": 3,
                   "Pastime_PlayGameOnPhone": 2, "Pastime_CheckSocialMedia": 2, "Pastime_PlayAmongUs": 2},
         react=[("Computer", "In the zone", "Happy", 1, 120)], learn=["Programming"]),
    dict(id="Stargazer", name="Stargazer",
         desc="Head in the stars. Uses telescopes a lot, is inspired by the night sky and learns Astronomy faster.",
         autonomy={"SkillActivity_UseTelescope": 5},
         react=[("Telescope", "Starstruck", "Inspired", 2, 240)], learn=["Astronomy"]),
    dict(id="NatureLover", name="Nature Lover",
         desc="Feels at home outdoors. Stops to smell the flowers, takes walks and is happier for it.",
         autonomy={"Town_SmellFlowers": 4, "Town_WalkLeisurely": 3, "Pastime_DigGroundForFun": 2},
         react=[("Nature", "Fresh air", "Happy", 2, 180)], learn=["Outdoorsiness"]),
    dict(id="Romantic", name="Romantic",
         desc="Always in love with love. Kisses, hugs and slow dances leave them feeling flirty.",
         autonomy={"Social_DanceIfOthersDance": 2},
         react=[("Romance", "Swept off their feet", "Flirty", 2, 180)]),
    dict(id="HotHeaded", name="Hot-Headed",
         desc="Has a short fuse. Gets angry out of nowhere now and then, and lets it out.",
         autonomy={"Emotion_KickSomethingAngrily": 3},
         react=[(("interval", 60, 0.15), "Short fuse", "Angry", 1, 60)]),
    dict(id="SocialButterfly", name="Social Butterfly",
         desc="Never met a stranger. Chats more often and is happy whenever they're in good company.",
         autonomy={r: 3 for r in SOCIAL_RULES},
         react=[("group", "Among friends", "Happy", 1, 60)]),
    dict(id="Loner", name="Loner",
         desc="Needs their space. Chats less, daydreams more and gets uncomfortable in groups.",
         autonomy=dict({r: -3 for r in SOCIAL_RULES}, Pastime_Daydream=3),
         react=[("group", "Craving alone time", "Uncomfortable", 1, 60)]),
]

# Spontaneous quirks: new idle-autonomy activities only Paras with the trait get. Each clones a game
# activity's requirements (minus `drop`ped requirement types, e.g. "only when hungry") and adds the
# trait, a cooldown and a random chance, so they happen out of the blue instead of on a schedule.
#   (source activity, cooldown minutes, score, requirement types to drop, extra requirements)
NIGHT = [("Type", 1000), ("TimeOfDayMinimum", 1140), ("TimeOfDayMaximum", 1439)]   # 7pm - midnight
QUIRKS = {
    "GymRat": [("Exercise_FlexMuscle", 180, 4, [181], []), ("SkillActivity_PushUpOnFloor", 240, 3, [], [])],
    "HotHeaded": [("Emotion_KickSomethingAngrily", 240, 4, [], [])],
    "MusicLover": [("Pastime_ListenToMusic", 180, 4, [], [])],
    "CouchPotato": [("Pastime_Daydream", 180, 3, [], [])],
    "Lazy": [("ReliefNeed_Nap", 360, 3, [202], [])],
    "NatureLover": [("Pastime_DigGroundForFun", 240, 3, [], []), ("Town_SmellFlowers", 120, 4, [], [])],
    "SocialButterfly": [("Social_TalkWith_CurrentHousehold", 90, 4, [], [])],
    "Loner": [("Emotion_CalmSelfInMirror", 240, 3, [], [])],
    "Techie": [("Pastime_PlayGameOnPhone", 180, 3, [], []), ("Pastime_CheckSocialMedia", 180, 3, [], [])],
    "Artsy": [("Pastime_Draw", 240, 4, [], [])],
    "Stargazer": [("SkillActivity_UseTelescope", 360, 5, [], [NIGHT])],
    "Glutton": [("ReliefNeed_EatSnack", 240, 3, [202], [])],
    "Romantic": [("Pastime_Daydream", 240, 3, [], [])],
}
QUIRK_CHANCE = 0.35
# Reactions to quirks that are interactions rather than actions: (trait, source activity, moodlet...)
QUIRK_REACT = [("Romantic", "Pastime_Daydream", "Daydreaming of love", "Flirty", 1, 120)]

# ------------------------------------------------------------------ helpers


def gid(*parts):
    """Stable 63-bit ID from a name, so rebuilding never changes IDs (saves keep working)."""
    h = hashlib.sha256(("ParaTraits/" + "/".join(str(p) for p in parts)).encode()).digest()
    return int.from_bytes(h[:8], "big") & 0x7FFFFFFFFFFFFFFF or 1


class W:
    """Writes manifest lines with 1-space-per-level indentation."""

    def __init__(self, setting):
        self.lines = ["#Setting." + setting]

    def f(self, depth, name, value=None):
        self.lines.append(" " * depth + "=" + name + ("" if value is None else ":" + str(value)))

    def add(self, depth, guid):
        self.lines.append(" " * depth + "@" + str(guid))
        self.f(depth + 1, "GUID", guid)

    def edit(self, depth, guid):
        self.lines.append(" " * depth + "g" + str(guid))

    def text(self):
        return "\n".join(self.lines) + "\n"


def copy_node(w, depth, node, seed):
    """Writes a copy of a game requirement subtree with fresh, stable GUIDs."""
    for c in node.children:
        if c.op == "=" and c.name == "GUID":
            continue
        if c.op == "=" and any(x.op in "ig" for x in c.children):          # array field
            w.f(depth, c.name)
            for i, el in enumerate(x for x in c.children if x.op in "ig"):
                w.add(depth + 1, gid(seed, c.name, i))
                copy_node(w, depth + 2, el, (seed, c.name, i))
        elif c.op == "=":
            w.f(depth, c.name, c.arg)
            if c.children:
                copy_node(w, depth + 1, c, (seed, c.name))


def load_game_ids(game_settings):
    """Resolves rule and action names to IDs from the installed game."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from setting import parse
    au = parse(os.path.join(game_settings, "Autonomy.setting")).children[0]
    load_game_ids.rule_nodes = {e.val("DisplayName"): e for e in au.get("ScoreBasedIdleAutonomyRules").children if e.op in "ig"}
    rules = {e.val("DisplayName"): int(e.val("GUID")) for e in au.get("ScoreBasedIdleAutonomyRules").children if e.op in "ig"}
    ac = parse(os.path.join(game_settings, "Actions.setting")).children[0]
    arr = max(ac.children, key=lambda c: len(c.children))
    actions = {}
    for e in arr.children:
        if e.op in "ig":
            actions.setdefault(e.val("DisplayName"), int(e.val("GUID")))
    return rules, actions


def action_ids(key, actions):
    v = ACTION[key]
    v = v if isinstance(v, list) else [v]
    return [x if isinstance(x, int) else actions[x] for x in v]


# ------------------------------------------------------------------ build


def build(out_dir, game_settings):
    rules, actions = load_game_ids(game_settings)
    missing = [r for r in RULES if r not in rules]
    if missing:
        raise SystemExit("autonomy rules not found in this game version: %s" % missing)

    mod_guid = gid("mod")
    folder = os.path.join(out_dir, "%s_%d.mod" % (MOD_FOLDER, mod_guid))
    os.makedirs(os.path.join(folder, "Settings"), exist_ok=True)

    pers, se, bl, auto, tr = W("Personalities"), W("StatusEffects"), W("BrainLogic"), W("Autonomy"), W("Translations")
    pers.f(1, "PersonalityTraits")
    se.f(1, "AllStatusEffects")
    bl.f(1, "BrainTriggersAndLogics")
    auto.f(1, "ScoreBasedIdleAutonomyRules")
    tr.f(1, "Items")
    translations = []
    modifiers = {}   # rule -> [(trait guid, score)]

    def moodlet(trait_id, label, emotion, value):
        name = "PT_%s_%s" % (trait_id, "".join(ch for ch in label.title() if ch.isalnum()))
        g = gid("se", name)
        if g in made_moodlets:
            return g
        made_moodlets.add(g)
        se.add(2, g)
        se.f(3, "DisplayName", name)
        se.f(3, "Effects")
        se.add(4, gid("se", name, "fx"))
        se.f(5, "EffectType", 200)
        se.f(5, "EmotionGUID", EMO[emotion])
        se.f(5, "Value", value)
        translations.append(("StatusEffect_" + name, label))
        return g

    made_moodlets = set()

    def rule(name, triggers, trait_guid, outcome, extra_reqs=()):
        g = gid("bl", name)
        bl.add(2, g)
        bl.f(3, "DisplayName", name)
        bl.f(3, "Triggers")
        for i, t in enumerate(triggers):
            bl.add(4, gid("bl", name, "trigger", i))
            for k, v in t:
                bl.f(5, k, v)
        bl.f(3, "Logic")
        bl.add(4, gid("bl", name, "if"))
        bl.f(5, "LogicType", 1)                       # IF
        bl.f(5, "ContextRequirement")
        bl.add(6, gid("bl", name, "has-trait"))
        bl.f(7, "Type", 190)                           # has personality trait
        bl.f(7, "PersonalityTrait", trait_guid)
        for j, req in enumerate(extra_reqs):
            bl.add(6, gid("bl", name, "req", j))
            for k, v in req:
                bl.f(7, k, v)
        bl.add(4, gid("bl", name, "do"))
        bl.f(5, "Outcome")
        for k, v in outcome:
            bl.f(6, k, v)

    for t in TRAITS:
        tg = gid("trait", t["id"])
        dn = "PT_" + t["id"]
        pers.add(2, tg)
        pers.f(3, "DisplayName", dn)
        pers.f(3, "PersonalityTraitCategory", LIFESTYLES_CATEGORY)
        pers.f(3, "Type", 2)                          # toggle, shown in the Lifestyles section
        translations += [("Trait_" + dn, t["name"]), ("TraitDescription_" + dn, t["desc"])]

        for r, score in t.get("autonomy", {}).items():
            modifiers.setdefault(r, []).append((tg, score, t["id"]))

        for i, (trig, label, emotion, value, minutes) in enumerate(t.get("react", [])):
            sg = moodlet(t["id"], label, emotion, value)
            outcome = [("Type", 290), ("StatusEffectGUID", sg),
                       ("StatusEffectHasOverrideDuration", "True"), ("StatusEffectOverrideDuration", minutes)]
            extra = ()
            if trig == "group":
                triggers = [[("MemoryLogType", 800), ("MemoryLogTrigger", 1)]]          # while in a social group
            elif isinstance(trig, tuple) and trig[0] == "interval":
                triggers = [[("MemoryLogType", 901), ("TimeInterval", trig[1])]]
                extra = [[("Type", 5010), ("Rule", 1), ("Value", trig[2]), ("RandomSeedType", 1)]]   # random chance
            else:
                triggers = [[("MemoryLogType", 0), ("ActionGUID", a), ("MemoryLogActionTrigger", 2)]   # action ended
                            for a in action_ids(trig, actions)]
            rule("PT_%s_React%d" % (t["id"], i), triggers, tg, outcome, extra)

        if t.get("learn"):
            name = "PT_%s_FastLearner" % t["id"]
            g = gid("se", name)
            se.add(2, g)
            se.f(3, "DisplayName", name)
            se.f(3, "Effects")
            for s in t["learn"]:
                se.add(4, gid("se", name, s))
                se.f(5, "EffectType", 1)               # skill learning speed
                se.f(5, "SkillGUID", SKILL[s])
                se.f(5, "Value", 1)
            translations.append(("StatusEffect_" + name, "%s talent" % t["name"]))
            # refreshed every 30 minutes while the Para has the trait, and wears off if it's removed
            rule(name, [[("MemoryLogType", 901), ("TimeInterval", 30)]], tg,
                 [("Type", 290), ("StatusEffectGUID", g),
                  ("StatusEffectHasOverrideDuration", "True"), ("StatusEffectOverrideDuration", 60)])

        for need, rate in t.get("drain", {}).items():
            rule("PT_%s_%sDrain" % (t["id"], need), [[("MemoryLogType", 2000)]], tg,
                 [("Type", 10), ("NeedToAffect", NEED[need]), ("NeedDecayValue", rate)])

    trait_guid = {t["id"]: gid("trait", t["id"]) for t in TRAITS}
    quirk_count = 0
    for tid, quirks in QUIRKS.items():
        tg = trait_guid[tid]
        for src, cooldown, score, drop, extra in quirks:
            node = load_game_ids.rule_nodes[src]
            inject = node.get("InteractionToInject").val("InjectedInteraction")
            name = "PT_%s_Quirk_%s" % (tid, src)
            qg = gid("quirk", name)
            auto.add(2, qg)
            auto.f(3, "DisplayName", name)
            auto.f(3, "Score", score)
            auto.f(3, "InteractionToInject")
            auto.f(4, "InjectedInteraction", inject)
            auto.f(3, "ContextRequirements")
            reqs = [[("Type", 190), ("PersonalityTrait", tg)],                                  # has the trait
                    [("Type", 290), ("Interaction", inject), ("Value", 1), ("TimePeriodSinceInMinutes", cooldown)],  # cooldown
                    [("Type", 5010), ("Rule", 1), ("Value", QUIRK_CHANCE), ("RandomSeedType", 1)]] + list(extra)    # chance
            for i, req in enumerate(reqs):
                auto.add(4, gid("quirk", name, "req", i))
                for k, v in req:
                    auto.f(5, k, v)
            for i, q in enumerate(node.items("ContextRequirements")):
                if int(q.val("Type", "0")) in drop or q.val("Type") == "290":        # our own cooldown replaces theirs
                    continue
                auto.add(4, gid("quirk", name, "copy", i))
                copy_node(auto, 5, q, ("quirk", name, "copy", i))
            quirk_count += 1

    for tid, src, label, emotion, value, minutes in QUIRK_REACT:
        inject = int(load_game_ids.rule_nodes[src].get("InteractionToInject").val("InjectedInteraction"))
        sg = moodlet(tid, label, emotion, value)
        rule("PT_%s_QuirkReact_%s" % (tid, src),
             [[("MemoryLogType", 1), ("InteractionGUID", inject), ("MemoryLogActionTrigger", 2)]], trait_guid[tid],
             [("Type", 290), ("StatusEffectGUID", sg), ("StatusEffectHasOverrideDuration", "True"),
              ("StatusEffectOverrideDuration", minutes)])
    print("  spontaneous quirks=%d" % quirk_count)

    for r, mods in modifiers.items():
        auto.edit(2, rules[r])
        auto.f(3, "ScoreModifiers")
        for tg, score, tid in mods:
            mg = gid("auto", r, tid)
            auto.add(4, mg)
            auto.f(5, "Modifier", score)
            auto.f(5, "ContextRequirement")
            auto.f(6, "GUID", gid("auto", r, tid, "req"))
            auto.f(6, "Type", 190)
            auto.f(6, "PersonalityTrait", tg)

    for key, value in translations:
        tg = gid("tr", key)
        tr.add(2, tg)
        tr.f(3, "Key", key)
        tr.f(3, "Value", value)
    tr.edit(2, TRANSLATION_LIFESTYLES_TITLE)
    tr.f(3, "Value", "Lifestyle & Traits")

    for setting, w in (("Personalities", pers), ("StatusEffects", se), ("BrainLogic", bl),
                       ("Autonomy", auto), ("Translations", tr)):
        path = os.path.join(folder, "Settings", setting + ".setting")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(w.text())
        with open(path + ".meta", "w", encoding="utf-8", newline="\n") as f:
            f.write("GUID:%d\nType:203\nIsSettingType:True\nSettingType:Setting.%s\n" % (gid("file", setting), setting))

    # Mod info file the game reads (name, Workshop tags and description) and the preview image.
    here = os.path.dirname(os.path.abspath(__file__))
    desc_path = os.path.join(here, "workshop_description.txt")
    desc = open(desc_path, encoding="utf-8").read().strip() if os.path.exists(desc_path) else "Sims-style traits for Paralives."
    meta = os.path.join(folder, os.path.basename(folder) + ".meta")
    with open(meta, "w", encoding="utf-8", newline="\n") as f:
        f.write("GUID:%d\nType:401\nModName:%s\nEnabled:True\nIsSystemMod:False\n" % (mod_guid, MOD_NAME))
        f.write("CreationTime:639300720000000000\nLastEditTime:639300720000000000\nLastUploadTime:0\n")
        f.write("IsFromWorkshop:False\nPublishedFileId:0\nCreatorId:\n")
        f.write("WorkshopUserTags:Mod_LiveMode_LiveMode,Mod_General_Misc\n")
        f.write("WorkshopDescription:" + desc + "\n")
    thumb = os.path.join(here, "thumbnail.png")
    if os.path.exists(thumb):
        import shutil
        shutil.copyfile(thumb, os.path.join(folder, os.path.basename(folder) + ".thumbnail"))

    print("built", folder)
    print("  traits=%d moodlets=%d rules=%d autonomy-rules-changed=%d translations=%d" % (
        len(TRAITS), sum(1 for l in se.lines if l.startswith("  @")), sum(1 for l in bl.lines if l.startswith("  @")),
        len(modifiers), len(translations) + 1))
    return folder, mod_guid


if __name__ == "__main__":
    game = os.environ.get("PARALIVES_SETTINGS", r"C:\Program Files (x86)\Steam\steamapps\common\Paralives\Main.mod\Settings")
    build(sys.argv[1] if len(sys.argv) > 1 else "out", game)
