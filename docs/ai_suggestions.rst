AI handling suggestions
=======================

This optional feature lets a staff member request a draft handling suggestion
from an OpenAI-compatible chat-completions endpoint. It is disabled by default.
The request is made only after the staff member presses the button on a ticket
page. It never changes ticket fields, assignments, follow-ups or status.

Configuration
-------------

Set these Django settings in the host project:

.. code-block:: python

   import os

   HELPDESK_AI_ENABLED = True
   HELPDESK_AI_CHAT_COMPLETIONS_URL = "https://provider.example/v1/chat/completions"
   HELPDESK_AI_MODEL = "your-model"
   HELPDESK_AI_API_KEY = os.environ["HELPDESK_AI_API_KEY"]
   HELPDESK_AI_TIMEOUT_SECONDS = 30

The demo project reads the same values from environment variables. For example,
in PowerShell:

.. code-block:: powershell

   $env:HELPDESK_AI_ENABLED = "true"
   $env:HELPDESK_AI_CHAT_COMPLETIONS_URL = "http://127.0.0.1:11434/v1/chat/completions"
   $env:HELPDESK_AI_MODEL = "qwen3.5:4b"
   $env:HELPDESK_AI_TIMEOUT_SECONDS = "30"
   $env:HELPDESK_AI_REASONING_EFFORT = "none"
   py -3.14 -m uv run manage.py runserver 127.0.0.1:8080

The endpoint and model must both be set. API key is optional for local providers.
Use a trusted provider and review your organization's data-handling policy before
sending ticket content to it: ticket title, description and selected prior
resolutions leave the application in the request.

How it works
------------

The service considers at most 300 recent resolved or closed tickets that the
staff member is authorized to read. It ranks title and description overlap
using character pairs, then sends at most three examples to the provider. This
retrieval is a small, dependency-free baseline, not a semantic embedding
search. Prior ticket IDs remain visible in the result so staff can inspect the
evidence. Unavailable or malformed provider responses display an error without
changing the ticket.

The provider call uses an eight-second timeout by default; deployments may set
``HELPDESK_AI_TIMEOUT_SECONDS`` for slower local models.
``HELPDESK_AI_REASONING_EFFORT`` is optional and only sent when configured.
Source fields and output are truncated to bound request size. Generated text is rendered as escaped plain text.
The feature does not measure suggestion quality automatically. Evaluate on
labeled local tickets before treating its advice as reliable.

Tests
-----

Run the focused and full suites:

.. code-block:: powershell

   py -3.14 -m uv run quicktest.py tests.test_ai_suggestions
   py -3.14 -m uv run quicktest.py
