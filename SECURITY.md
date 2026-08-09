# Security Policy

## Supported Versions

We only support the latest django-helpdesk version.

## Reporting a Vulnerability

If you believe you have discovered a bug impacting security in a supported version, please DO NOT file a Issue / Bug Report for it publicly.

Instead, please send details to <uhurusurfa@gmail.com>. Please be sure to include "django-helpdesk security issue" in the subject line for fastest response.

Once reported, we'll be in touch to confirm the issue and work toward releasing a patch as soon as possible.

After a patch has been released, a new release will be tagged and uploaded to PyPi, etc. At that time, details of the issue will be announced publicly.

Users are always highly encouraged to upgrade to the latest bugfix release as soon as possible.

## Handling a report

This section is for maintainers. It exists because the substance of a fix is the
easy part: what goes wrong is the sequencing, and it goes wrong when no single
person is holding the whole chain.

**Assign an owner as soon as a report arrives.** One named maintainer, responsible
from intake through to publication. Everything below is theirs to drive, not to
delegate and hope.

1. **Open a draft security advisory early**, under Security > Advisories. Credit
   the reporter and add them as a collaborator on the advisory so they can review
   the description and the severity. They usually know the issue better than we
   do, and they will catch an inaccurate write-up before it is public.

2. **Request the CVE at draft stage**, not at the end. GitHub quotes up to three
   working days to review the request, and requesting it discloses nothing, so it
   may as well run in parallel with the fix. Publishing before the identifier is
   assigned is fine: it gets attached to the advisory when their review completes.

3. **Fill in the affected version range honestly.** Work out when the vulnerable
   code was actually introduced rather than assuming it was recent, and make the
   upper bound match the version that will carry the fix. A range that disagrees
   with the patched version tells Dependabot that people already on the previous
   release are safe when they are not.

4. **Build the fix in the advisory's temporary private fork**, reviewed by a
   second maintainer. Put the version bump in the same pull request as the fix,
   so no separate bump pull request is needed afterwards. Add regression tests
   that fail without the fix.

5. **Merge, tag, and confirm the release is live on PyPI, in that order and
   without pausing.** Merging is what makes the vulnerability public, because the
   commit and its message describe it. From that moment until the release is
   installable, the issue is disclosed with no fix available. That window should
   be minutes.

6. **Chase credit acceptance before publishing.** Credits that have not been
   accepted never appear in the published advisory, and the record ends up
   showing fewer people than were actually involved.

7. **Publish the advisory last**, once the version it names can actually be
   installed.

Steps 5 and 7 are the ones worth re-reading. Publishing an advisory that points
at a version nobody can install is worse than publishing a day later.

If the fix turns out to be incomplete after release, treat the follow-up as its
own pass through this list rather than amending the published advisory in place.
