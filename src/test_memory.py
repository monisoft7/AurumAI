from knowledge.memory import Memory


memory = Memory()

memory.add(

    "CPI",

    {

        "effect_on_gold": "Bullish",

        "confidence": 0.72,

    },

)

print(memory.load())