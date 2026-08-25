# Security Policy

## Supported Versions

We only support the latest django-helpdesk version.

## Reporting a Vulnerability

If you believe you have discovered a bug impacting security in a supported version, please DO NOT file an Issue or Bug Report for it publicly.

Use [private vulnerability reporting](https://github.com/django-helpdesk/django-helpdesk/security/advisories/new) instead, from the Security tab of this repository.
It opens a draft security advisory that only the maintainers can see, and it keeps the whole exchange in one place.
You will be a collaborator on that draft, so you can review how we describe the issue and the severity we assign to it before any of that becomes public.
It also means your report does not depend on one person reading their email.

If you cannot use that form, for instance because you have no GitHub account, send the details to <uhurusurfa@gmail.com> and include "django-helpdesk security issue" in the subject line.

Either way we will confirm the issue and work toward releasing a patch as soon as possible.

Details of the issue are announced publicly once a fix has been released and tagged on PyPI, and not before.

Users are always highly encouraged to upgrade to the latest bugfix release as soon as possible.

## Handling a report

This section is for maintainers.
It exists because the substance of a fix is the easy part: what goes wrong is the sequencing, and it goes wrong when no single person is holding the whole chain.

**Assign an owner as soon as a report arrives.**
One named maintainer, responsible from intake through to publication.
Everything below is theirs to drive, not to delegate and hope.

1. **Start from a draft security advisory.**
   A report that came through private vulnerability reporting already created one, with the reporter as a collaborator, so there is nothing to open: take it over and credit them.
   For a report that arrived by email, open the draft yourself under Security > Advisories, credit the reporter and add them as a collaborator.
   Either way they usually know the issue better than we do, and they will catch an inaccurate write-up before it is public.

2. **Request the CVE at draft stage**, then stop thinking about it.
   Requesting it discloses nothing, so it may as well run in parallel with the fix, but do not treat the identifier as a prerequisite for anything.
   GitHub's own support told us in August 2026 that CVE requests are being processed in order of arrival with a turnaround of about three weeks, that individual requests cannot be expedited, and, most usefully, that **Dependabot alerts are driven from the advisory rather than from the CVE assignment**.
   Publishing therefore protects users immediately, whether or not an identifier exists yet, and the CVE is the external record rather than the thing that warns anybody.
   Two consequences worth knowing.
   Waiting for the identifier before publishing buys nothing and delays the alerts, so do not do it.
   And another CNA may assign one from the published advisory before GitHub's review completes, with their own severity and wording, as VulnCheck did for GHSA-q46c-8w98-fq2g with CVE-2026-73531 five days after we published; if that happens, adopt their identifier rather than arguing a difference.

3. **Fill in the affected version range honestly.**
   Work out when the vulnerable code was actually introduced rather than assuming it was recent, and make the upper bound match the version that will carry the fix.
   A range that disagrees with the patched version tells Dependabot that people already on the previous release are safe when they are not.

4. **Build the fix in the advisory's temporary private fork**, reviewed by a second maintainer.
   Put the version bump in the same pull request as the fix, so no separate bump pull request is needed afterwards.
   Add regression tests that fail without the fix.

5. **Merge, tag, and confirm the release is live on PyPI, in that order and without pausing.**
   Merging is what makes the vulnerability public, because the commit and its message describe it.
   From that moment until the release is installable, the issue is disclosed with no fix available.
   That window should be minutes.

6. **Chase credit acceptance before publishing.**
   Credits that have not been accepted never appear in the published advisory, and the record ends up showing fewer people than were actually involved.

7. **Publish the advisory last**, once the version it names can actually be installed.

Steps 5 and 7 are the ones worth re-reading.
Publishing an advisory that points at a version nobody can install is worse than publishing a day later.

If the fix turns out to be incomplete after release, treat the follow-up as its own pass through this list rather than amending the published advisory in place.
