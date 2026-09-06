# Safe Exam Browser (SEB) integration for Assignments

## Problem

Assignments already support a couple of soft anti-cheating options, like `anti_copy_paste`, which blocks paste events on code and text inputs. That's fine for casual coursework, but it's easy to get around and doesn't help at all for graded or proctored exams.

Safe Exam Browser is the standard tool schools use for locked-down exams. Most LMS platforms (Moodle, Canvas, etc.) support it in some form. LearnHouse doesn't have anything like it right now, and I think it's worth adding.

## Proposed design

I'd rather extend the existing per-assignment flag pattern on `AssignmentBase` (in `apps/api/src/db/courses/assignments.py`) than build something new from scratch. Concretely:

- `require_safe_exam_browser: bool = False`, an opt-in per assignment, same idea as `anti_copy_paste`.
- `seb_config_key: Optional[str]`, the Browser Exam Key that SEB computes from its `.seb` config file. We just verify against this, we don't need to store SEB's own config.
- `seb_quit_password: Optional[str]`, optional, so a teacher can unlock or quit SEB once the exam window is over.

**Enforcement**: SEB sends an `X-SafeExamBrowser-ConfigKeyHash` header (and on older versions, `X-SafeExamBrowser-RequestHash`) with every request. When `require_safe_exam_browser` is on, the assignment submission endpoints would recompute the expected hash from `seb_config_key` plus the request URL, and reject anything that's missing or doesn't match with a 403. That's the one part of this that can't be faked from the client. Everything else, like a blocking screen in the UI, is a deterrent, in the same category as `anti_copy_paste`, not a real guarantee.

**Setup flow**: a teacher turns on the flag in the assignment editor, and the backend generates a downloadable `.seb` config file (SEB uses an XML plist format) with the exam URL and computed key already filled in. Students install it once and use it to open the assessment.

## Questions for maintainers

1. Should this be a core feature, or gated like Payments and SSO under the Enterprise tier? `AssignmentOrgConfig` in `organization_config.py` already has an `enabled` switch we could reuse for an org-level toggle either way.
2. Is header-hash verification good enough as the security bar here? It's what SEB itself supports, and it's what other LMS integrations lean on too, but it's a deterrent against casual bypass, not a cryptographic guarantee. I want to be upfront about that rather than let the UI copy oversell it.
3. Is there already internal thinking on proctoring or exam-integrity features that this should line up with, so it doesn't end up stepping on a bigger plan that's already in motion?

Happy to turn this into a full issue and start building once there's a steer on scope.
