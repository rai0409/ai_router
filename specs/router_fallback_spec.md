1. Goal

Introduce role-based fallback handling in router.py so that when a provider assigned to a role fails, the router automatically attempts the next provider for that role and continues operating, while preserving all existing behavior for successful executions.

2. Scope
In scope

Detecting provider failure strictly via raised exceptions during role-based routing.

Sequentially attempting fallback providers for the same role.

Centralizing fallback control logic exclusively within router.py.

Out of scope

Any changes to provider implementations.

Any changes to configuration formats, rules files, or prompt templates.

Any retry, backoff, or recovery mechanisms, including retrying the same provider.

Introducing new dependencies, logging behavior, or altering public interfaces beyond router.py.

3. Definitions

Role
A role is a string identifier used by the router to select a group of providers.
Roles are provided to the router by existing upstream logic and are not defined or modified by this specification.
Examples include (but are not limited to):
spec_llm, impl_llm, review_llm, review_llm_light.

Resolved provider list for a role
The ordered list of provider call targets that the router currently resolves for a given role using existing code paths.
This specification must not change:

how this list is defined,

how it is loaded,

how its order is determined.

Configured order
The exact order of providers as returned by the existing provider resolution logic.
This order must be preserved and interpreted as the fallback priority order.

Provider failure
A provider failure is defined strictly as the provider raising an exception derived from Exception.
Return values, including None or empty results, must not be interpreted as failures.

4. Functional Requirements

The router must route requests strictly based on role identifiers, not model names.

For a given role, the router must obtain the existing resolved provider list using the current resolution mechanism, without modification.

If the resolved provider list for a role is empty, the router must immediately raise a runtime exception indicating that no providers are available for the role.

Providers must be attempted sequentially in the configured order of the resolved provider list.

When invoking a provider, the router must catch only exceptions derived from Exception.

Upon catching such an exception, the router must proceed to the next provider in the list.

The router must return immediately upon the first successful provider execution, preserving all existing success-path behavior.

If all providers assigned to the role fail, the router must re-raise the last exception encountered without modifying its type or message.

A provider must be attempted at most once per request; retrying the same provider is not permitted.

5. Non-Functional Requirements

Existing routing behavior for successful provider executions must remain unchanged, including return values and any existing side effects.

No changes may be made to any files other than router.py.

No new configuration formats, logging behavior, metrics, or external dependencies may be introduced.

The implementation must be deterministic and reproducible given the same provider order and provider behavior.

Error handling must be explicit and limited to exception-based failure detection.

The router must not alter, wrap, or replace exceptions except for re-raising the last encountered exception when all providers fail.

The fallback mechanism must not introduce any new observability side effects (e.g., logging) beyond what already exists.

6. Files to Modify

router.py

7. Step-by-Step Implementation Plan

Identify the role-based routing entry point in router.py.

Locate the existing logic that resolves the ordered provider list for a given role.

If the resolved provider list is empty, raise an exception immediately.

Define a single local variable outside the provider loop to store the most recent failure exception.

Iterate through the resolved provider list in its existing order:

Invoke the provider using the existing invocation mechanism.

If the invocation succeeds, return the result immediately.

If the invocation raises an exception derived from Exception, store it in the local failure variable and continue to the next provider.

After all providers have been attempted and none succeeded, re-raise the stored failure exception without modification.

Verify that no provider code, rules files, or prompt templates were modified.

8. Completion Checklist

 Providers are attempted sequentially by role when exceptions occur.

 Each provider is attempted at most once.

 Return values are never interpreted as failures.

 An empty provider list raises an exception immediately.

 Successful provider executions behave exactly as before.

 The last encountered exception is re-raised unchanged when all providers fail.

 Only router.py was modified.

 No new dependencies, logging, or configuration changes were introduced.
