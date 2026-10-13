"""RIA, the invoice-call voice agent.

A call runs as a pipeline, the way Vapi builds voice agents: OpenAI speech-to-text
(Smallest Pulse with RIA_STT=pulse) turns the customer's speech into text in the
conversation's language, gpt-4.1-mini
writes RIA's reply from that text and calls tools, and the cloned voice speaks it.
The model and every check in the app read the same transcript, so they can't
disagree about what the customer said.

    settings   .env values in one place
    script     prompts.py (instructions and fixed lines), reloaded per call
    languages  the conversation language and requests to change it
    dates      calendar, payment-date limits, date wording
    voice      speech-to-text, the model, the cloned voice, pre-made lines
    outcomes   outcome codes and how a result is saved
    agent      the conversation: tools and checks
    call       one phone call from pickup to hang-up
"""

# backend/.env is loaded before any module here reads a setting or opens the database
from ria.settings import BACKEND_DIR

__all__ = ["BACKEND_DIR"]
