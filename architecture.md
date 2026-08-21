
## Amendment (Step 21 Final Review): Streaming Now Routes Through the Conversation Controller

§34's "no component bypasses the Conversation Controller" and
"generation never bypasses validation" previously had an undocumented
exception: /chat/stream called Context/Reasoning/Generation directly,
skipping Validation and Reflection entirely, on the reasoning that
true token streaming and post-hoc full-text validation seemed
incompatible.

That exception has been closed, not merely documented. /chat/stream
now runs through handle_message_stream() in the Conversation
Controller: tokens still arrive live, but the complete accumulated
text is validated and reflected the instant streaming finishes, using
the same rules /chat always has. If validation fails, the
already-streamed text is not retracted (it was already shown to the
person) but the final event honestly marks it NOT VERIFIED -- the
same failure shape /chat already uses for an undelivered turn.

All four §36 Non-Negotiable Behavioural Guarantees now hold
universally across both /chat and /chat/stream, with no exceptions.
