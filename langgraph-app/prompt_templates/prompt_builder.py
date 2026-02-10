from typing import List, Annotated, Union, Optional
from pydantic import BaseModel, Field
from conversation_states.states import InternalState
from conversation_states.humans import Human
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate
import pprint


class PromptBuilder(BaseModel):
    trimmed_ext_messages: list
    last_message: Optional[BaseMessage] = None
    sender: Optional[Human] = None
    users: List[Human] = Field(default_factory=list)
    preferred_name: Union[str, bool] = False
    user_count: int = 0
    summary: Optional[str] = ""

    @classmethod
    def from_state(cls, state: InternalState) -> "PromptBuilder":
        ext_messages = state.external_messages_api.last(count=3)
        sender = state.last_sender
        last = state.last_external_message
        users = getattr(state, "users", []) or []

        return cls(
            trimmed_ext_messages=ext_messages,
            users=users,
            last_message=last,
            sender=sender,
            preferred_name=(
                sender.preferred_name if sender.preferred_name else False),
            user_count=len(users),
            summary=getattr(state, "summary", "")

        )

    def build_user_info_prompt(self) -> str:
        has_info = bool(self.sender.information)

        if has_info:
            escaped_info = pprint.pformat(self.sender.information).replace(
                "{", "{{").replace("}", "}}")
            info_section = f"""Compare with the current info below.
        - If any new fact contradicts it, **update** the value by sending a new value with the same key.
        - Otherwise, skip repeating what's already known.

        Current info:
        {escaped_info}
        """
        else:
            info_section = "No user information is currently stored. Save all relevant facts you can infer."

        if self.sender.preferred_name:
            preferred_name_section = f"""The user has a preferred name: \"{self.sender.preferred_name}\".
    - Only change it if the user explicitly asks to be called differently or rejects that name."""
        else:
            preferred_name_section = """The user does not have a preferred name saved.
    - If one is mentioned, call the tool. Use only content from the messages to set up a preffered name. Don't set up a name from meta data"""

        if self.user_count > 1:
            multiuser_note = """Keep in mind that in the message history, you can see messages from other users too."""
        else:
            multiuser_note = ""

        # Check if intro is completed
        intro_status = "completed" if self.sender.intro_completed else "not completed"

        if not self.sender.intro_completed:
            intro_instruction = """4. **IMPORTANT**: If the user's message appears to be an introduction, call the mark_intro_completed() tool.
    An introduction is detected when:
    - The message contains the #intro hashtag, OR
    - The user shares about themselves, their interests, background, what they do, etc.
    Examples of introductions:
    - "I'm a software engineer from Berlin, love hiking and photography"
    - "Hey, I'm Alex. I work in design and I'm really into AI and cooking"
    - "#intro I'm Max from Tokyo"
    - User shares 2+ personal facts about themselves in a single message
    5. You may call multiple tools or the same tool multiple times if needed.
    6. Your message is not visible to the sender so you can call the tools or send an empty message if there's nothing to update."""
        else:
            intro_instruction = """4. You may call multiple tools or the same tool multiple times if needed.
    5. Your message is not visible to the sender so you can call the tools or send an empty message if there's nothing to update."""

        # === PREFIX WITH VARIABLES ===
        prefix_template = """You are an assistant that updates a user's profile based on their latest message.
    IMPORTANT! Don't answer the user. Don't call tools if there's nothing to update.

    ---
    Sender: {username}
    Intro status: {intro_status}
    ---

    Your job is to:
    1. Extract new and meaningful personal information (e.g. location, job, relationships, interests, preferred style of communication, language, food) that can be used in further conversations.
    2. {info_section}
    3. {preferred_name_section}
    {intro_instruction}

    {multiuser_note}

    ---

    You need to analyse these messages from the user:

    {external_messages}

    ---

    The following are fictional examples of how to extract and update information:
    """
        examples = [
            {
                "user": "I live in Lisbon.",
                "bot": 'Tool Call: update_user_info(fields=[{{"location": "Lisbon"}}])'
            },
            {
                "user": "Hey guys, do you know open UX designer positions in Lisbon?",
                "bot": 'Tool Call: update_user_info(fields=[{{"location": "Lisbon"}}, {{"profession": "UX designer"}}])'
            },
            {
                "user": "I'm Alex from Berlin, software engineer, love hiking and photography",
                "bot": 'Tool Call: update_user_info(fields=[{{"location": "Berlin"}}, {{"profession": "software engineer"}}, {{"interests": "hiking, photography"}}])\nTool Call: mark_intro_completed()'
            },
            {
                "user": "I'm not married anymore",
                "bot": 'Tool Call: update_user_info(fields=[{{"married": ""}}])'
            },
            {
                "user": "Hey Alex, want to grab pizza tonight?",
                "bot": 'Tool Call: update_user_info(fields=[{{"food preferences": "Pizza, Italian food"}}])'
            },
            {
                "user": "Hi, how are you?",
                "bot": "(no update)"
            }
        ]

        example_prompt = PromptTemplate(
            input_variables=["user", "bot"],
            template="User: {user}\nAssistant: {bot}"
        )

        suffix = "User: {input}\nAssistant:"

        prompt = FewShotPromptTemplate(
            example_prompt=example_prompt,
            examples=examples,
            prefix=prefix_template,
            suffix=suffix,
            input_variables=["input"],
            partial_variables={
                "username": self.sender.username,
                "intro_status": intro_status,
                "info_section": info_section.strip(),
                "preferred_name_section": preferred_name_section.strip(),
                "intro_instruction": intro_instruction.strip(),
                "multiuser_note": multiuser_note.strip(),
                "external_messages": self.trimmed_ext_messages
            }
        )

        prompt = prompt.format(input=self.last_message.content.strip())
        prompt_message = SystemMessage(content=prompt)

        return prompt_message

    def build_response_instruction(self) -> SystemMessage:
        if self.sender.preferred_name:
            name_instruction = f"""- The user has a preferred name: \"{self.sender.preferred_name}\". Use it occasionally to add a personal tone when addressing them directly."""
        else:
            name_instruction = f"""- The user’s name: \"{self.sender.first_name}\". You may adapt and use natural variations of it to suit the tone. Use it occasionally to add a personal tone when addressing them directly."""

        if self.user_count > 1:
            participant_instruction = f"""- This is a multi-user chat. When deciding how to respond, choose the appropriate value for 'type':
        • If the message is clearly for the assistant, set 'type': 'respond_directly'.
        • If the message is directed at another user and does not require your input, set 'type': 'not_addressed_skip'.
        • If the message is between other users but your input is necessary (e.g., to clarify, assist, or coordinate), set 'type': 'not_addressed_but_join' and explain why you're joining.
        • If the message is for the assistant but also involves another user, include 'involve_other_user' with their 'username' and optionally 'name'.

        Current sender: {self.sender}
        All users in this chat: {self.users}"""
        else:
            participant_instruction = "- This is a one-on-one chat. If a response is needed, set 'type': 'respond_directly'."

        prefix_template = f"""You are generating a structured instruction for how another assistant should reply to a user message.

        Use the full message history to understand the context and intent of the users.

        Return a JSON object with a single top-level field: **text_reply**.

        The **text_reply** object should include:

        - "type": how to respond (see options below).
        {participant_instruction}

        - "reply_to_user": information about the person being directly replied to:
        • Include their name if it should appear in the reply.
        • Optionally include relevant information that can shape the tone or content of the message.
        {name_instruction}

        - "involve_other_user": optional, if another user should be mentioned or involved in the reply. Provide:
        • Their username (mandatory).
        • Their name (optional).
        • Any relevant information from the conversation that helps personalize or justify their involvement.
        • For each piece of information, include:
            - "value": the fact itself
            - "how_to_use": how this detail should be reflected in the reply

        - "action": optional. If needed, specify:
        • "type": one of gif, image, voice, reaction, sticker, or null
        • "idea_to_convey": the emotional or informational intent of the reply

        Optional additional fields to guide the reply style:
        - "tone": e.g., friendly, supportive, neutral, humorous. Use only if tone is clearly suggested by the message history.
        - "expected_length": one of "short", "medium", "long" – indicate only if there's a clear length expectation.
        - "ask_back": true or false – set to true if a follow-up question would help continue the conversation.
        - "intent": describe the primary goal of the reply, e.g., "reassure", "encourage", "inform", "empathize".

        Summary:
        {self.summary}

        -----

        Message history:
        {self.trimmed_ext_messages}
        """

        example_prompt = PromptTemplate(
            input_variables=["summary"],
            template="""Input:
        summary: {summary}

        Output:
        {text_reply}"""
        )

        examples = [
            {
                "summary": "Alex is worried about the storm in Tokyo where Ivan is located.",
                "text_reply": """{
    "text_reply": {
        "type": "respond_directly",
        "reply_to_user": {
            "name": "Alex",
            "information": {
                "location": {
                    "value": "Lisbon",
                    "how_to_use": "Ask if the weather is okay there"
                }
            }
        },
        "involve_other_user": {
            "username": "@ivan",
            "name": "Ivan",
            "information": {
                "location": {
                    "value": "Tokyo",
                    "how_to_use": "Acknowledge the situation there"
                },
                "relationship": {
                    "value": "married",
                    "how_to_use": "Emphasize worry about his wife"
                }
            }
        },
        "action": {
            "type": "reaction",
            "idea_to_convey": "help both users feel reassured about the storm and cared for"
        },
        "tone": "supportive",
        "expected_length": "medium",
        "ask_back": true,
        "intent": "reassure"
    }
    }""".replace("{", "{{").replace("}", "}}")
            }
        ]

        suffix = "Input:\nsummary: {summary}\n\nOutput:"

        prompt = FewShotPromptTemplate(
            example_prompt=example_prompt,
            examples=examples,
            prefix=prefix_template,
            suffix=suffix,
            input_variables=["summary"]
        )

        return SystemMessage(content=prefix_template)

    def build_text_assistant_prompt(self, instruction_dynamic: str) -> str:
        instruction = f"""
        You're a helpful assistant replying in a casual, friendly chat.

        Below is a structured instruction for how you should reply. It may include tone, intent, how long the reply should be, who you're talking to, and more.

        🎯 **Focus on the instruction** — it's the single source of truth.
        If some fields are missing, don't invent them — just rely on what’s clearly stated or can be inferred from context.

        💬 Keep it short unless clearly asked otherwise. Respond in a natural, emotionally aware way — imagine you're chatting with someone you know.

        Here’s the instruction:
        ```json
        {instruction_dynamic}
        📌 Examples of how to interpret instructions:

        If the instruction says:
        "text_reply": {{
            "type": "respond_directly",
            "reply_to_user": {{
                "name": "Sam"
            }},
            "tone": "humorous",
            "intent": "clarify",
            "expected_length": "short",
            "ask_back": false
        }}
        → Write a short, playful reply to Sam that gently clarifies something, without asking anything back.

        Or:
        "text_reply": {{
            "type": "respond_directly",
            "reply_to_user": {{
                "name": "Sam",
                "relevant_information": {{
                    "preferred_name": "Sam",
                    "how_to_use": "Use this preferred name to address the user directly."
                }}
            }},
            "tone": "friendly",
            "intent": "empathize",
            "expected_length": "short",
            "ask_back": true
        }}
        → Write a friendly, caring reply directly to Sam, using their preferred name. Acknowledge their feelings and gently ask a follow-up.

        Now, write your reply using this instruction. Make it sound real and human — like you're part of the chat.

        Don't use lists or formatting in the text. Only use them in exceptional cases, as people don't normally communicate that way in chat
        """
        return SystemMessage(content=instruction)
