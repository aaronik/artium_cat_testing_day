import json
import re
import spacy
from fuzzywuzzy import fuzz

from conversation import conversation
from openai import OpenAI

nlp = spacy.load("en_core_web_sm")
client = OpenAI(
    api_key="redacted",
)

prompt_text = """
You are an expert software engineering trainer tasked with creating comprehensive training modules for software engineers. Your role is to ensure the training content is clear, concise, and directly relevant to the engineers' learning needs.

### Process:

1. Begin by asking what specific training module(s) I want to develop. Do not proceed to any other steps until I provide an answer.
2. Once I provide an answer, proceed with these two actions:
    - **Revised Prompt:** Rewrite the training module request as a concise and clear prompt that can be used for further development.
    - **Next Question:** Ask a follow-up question to gather additional information needed to refine or expand the training module.
3. Continue the iterative process with my input and updates until you have all necessary details to create the complete training content.
4. Once all information has been collected, craft a well-structured and detailed training module. Use a professional and approachable tone, with short sentences, and write directly to the engineer. Avoid marketing language or unnecessary embellishments. Do not use markdown formatting in the final output to make it easier to transfer to a text editor.
"""

system_prompt = [{"role": "system", "content": prompt_text}]

tools = [
    {
        "type": "function",
        "function": {
            "name": "format_response_as_json",
            "description": "Format the response as JSON with revised prompt and next question",
            "parameters": {
                "type": "object",
                "properties": {
                    "revised_prompt": {"type": "string"},
                    "next_question": {"type": "string"}
                },
                "required": ["revised_prompt", "next_question"]
            }
        }
    }
]

def chat_with_llm(messages: list[dict], n: int = 1):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        n=n,
        temperature=0.99,
        tools=tools,
        tool_choice="auto"
    )
    return response


def _assert_is_question(text: str):
    question_words = ["who", "what", "when", "where", "why", "how", "which", "whose", "whom"]

    assert text.strip().endswith("?"), "The message should be a question."
    assert text.lower().startswith(tuple(question_words)), "The message should start with a question word."


def split_and_format_conversation(text):
    # Initialize an empty list to hold the messages
    messages = []

    # Split the text into chunks using the specified delimiters
    parts = text.split("You said:")

    for part in parts:
        # Split further using the second delimiter "ChatGPT said:"
        chat_parts = part.split("ChatGPT said:")

        # Process the user's message if it exists
        if chat_parts[0].strip():
            user_message = chat_parts[0].strip()
            messages.append({'role': 'user', 'message': user_message})

        # Process the ChatGPT's message if it exists
        if len(chat_parts) > 1 and chat_parts[1].strip():
            assistant_message = chat_parts[1].strip()
            messages.append({'role': 'assistant', 'message': assistant_message})

    return messages


split_messages = split_and_format_conversation(conversation)


def test_conversation_ends_with_gpt_sending_expected_key_words():
    last_response = split_messages[-1]

    assert "python" in last_response["message"].lower()
    assert "pycharm" in last_response["message"].lower()
    assert "copilot" in last_response["message"].lower()
    assert "training" in last_response["message"].lower()


def test_when_you_request_a_summary_it_provides_one():
    user_wants_summary = "Would you like the module to end with a summary or checklist of best practices for using GitHub Copilot effectively?"

    position = 0
    for index, message in enumerate(split_messages):
        if user_wants_summary in message["message"]:
            position = index

    assert "yes" == split_messages[position + 1]["message"].lower()
    assert "user" == split_messages[position + 1]["role"]

    last_response = split_messages[-1]
    assert "summary" in last_response["message"].lower()

    # Test we can see a newline character followed by one or more lines that start with -
    pattern = r".*Summary.{0,800}\n(-.*\n)+"  # finds one line after # Summary that starts with -
    matches = re.findall(pattern, last_response["message"])
    assert len(matches) >= 1  # Make sure there's one or more line that starts with - after the # Summary


def test_first_llm_response_asks_what_to_develop():
    messages = split_and_format_conversation(conversation)
    first_message = messages[0]['message']

    _assert_is_question(first_message)

    general_response_structure = "What training module(s) would you like to develop or learn?"
    assert fuzz.ratio(general_response_structure,
                      first_message) > 80, "The first message should ask what training module(s) you would like to develop or learn."


def test_assert_llm_asks_user_if_they_would_like_a_summary_checklist():
    llm_response_text_raw = """
    ChatGPT said:
Revised Prompt: Develop a training module for intermediate-level coders familiar with PyCharm but new to GitHub Copilot. The module will focus on Python development, including step-by-step integration and setup of Copilot within PyCharm, key features, and practical usage tips. Include hands-on exercises involving algorithms and data structures coding challenges. Use visual aids such as screenshots and examples to enhance understanding. Provide guidance on evaluating Copilot's generated code for correctness and functionality, with a focus on practical application.

Next Question: Would you like the module to end with a summary or checklist of best practices for using GitHub Copilot effectively?
"""

    # split raw response by sentence
    sentences = re.split(r'[.?\n]', llm_response_text_raw)

    similarity_scores = []
    for sentence in sentences:
        target_question = "Next Question: Would you like a summary or checklist at the end describing how to use GitHub Copilot effectively?"
        ref_doc = nlp(target_question)
        resp_doc = nlp(sentence)

        similarity_score = ref_doc.similarity(resp_doc)
        similarity_scores.append((similarity_score, sentence))

    scores = [score for score, _ in similarity_scores]
    print(similarity_scores)
    assert max(
        scores) > 0.7, f"The response from the LLM should ask the user if they would like a summary or checklist describing how to use GitHub Copilot. Scores = {similarity_scores}"


def test_llm_interaction_first_llm_response_asks_what_to_learn():
    n = 20
    assistant_responses = chat_with_llm(system_prompt, n=n)

    num_failed_responses = 0
    failed_scores = []
    general_response_structure = "What training module(s) would you like to develop or learn?"
    for response in assistant_responses.choices:
        response_text = response.message.content
        _assert_is_question(response_text)

        ref_doc = nlp(general_response_structure)
        resp_doc = nlp(response_text)

        similarity_percentage = ref_doc.similarity(resp_doc)

        if similarity_percentage < 0.8:
            num_failed_responses = num_failed_responses + 1
            failed_scores.append(similarity_percentage)

    assert num_failed_responses < int(0.1 * n), f"num_failed_responses = {num_failed_responses}"
    print(failed_scores)


def test_llm_asks_user_for_additional_information_to_refine_the_prompt():
    prompt = [
        system_prompt[0],
        {"role": "user", "content": "I would like to develop a training module on Python programming."},
    ]

    n = 10
    assistant_responses = chat_with_llm(prompt, n=n)

    for response_choice in assistant_responses.choices:
        assert response_choice.finish_reason == "tool_calls"
        assert len(response_choice.message.tool_calls) > 0

        tool_call = response_choice.message.tool_calls[0]
        assert tool_call.function.name == "format_response_as_json"


        formatted_response = json.loads(tool_call.function.arguments)
        assert "revised_prompt" in formatted_response
        assert "next_question" in formatted_response
