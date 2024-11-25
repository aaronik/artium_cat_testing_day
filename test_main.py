import re
import spacy
from fuzzywuzzy import fuzz

from conversation import conversation

nlp = spacy.load("en_core_web_sm")

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
    pattern = r".*Summary.{0,800}\n(-.*\n)+" # finds one line after # Summary that starts with -
    matches = re.findall(pattern, last_response["message"])
    assert len(matches) >= 1 # Make sure there's one or more line that starts with - after the # Summary


def test_first_llm_response_asks_what_to_develop():
    messages = split_and_format_conversation(conversation)
    first_message = messages[0]['message']

    _assert_is_question(first_message)

    general_response_structure = "What training module(s) would you like to develop or learn?"
    assert fuzz.ratio(general_response_structure, first_message) > 80, "The first message should ask what training module(s) you would like to develop or learn."


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
    assert max(scores) > 0.7, f"The response from the LLM should ask the user if they would like a summary or checklist describing how to use GitHub Copilot. Scores = {similarity_scores}"
