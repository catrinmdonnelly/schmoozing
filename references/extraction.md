# Reading the card

## The fields

Produce one JSON object per card. Only `company` and one of `name` or `email` are required. Leave anything else blank rather than filling it with a guess.

```json
{
  "name": "Jo Bevan",
  "job_title": "Operations Director",
  "company": "Acme Fabrications Ltd",
  "email": "jo@acmefab.co.uk",
  "phone": "01632 960123",
  "mobile": "07700 900123",
  "website": "acmefab.co.uk",
  "address": "Unit 4, Riverside Industrial Estate, AB12 3CD",
  "linkedin": "https://www.linkedin.com/in/jo-bevan-123456",
  "socials": ["@acmefab"],
  "tagline": "Precision sheet metal since 1978",
  "event": "Riverside Business Expo",
  "met_date": "2026-09-09",
  "card_notes": "Handwritten on the back: send the quoting thing",
  "uncertain": ["email, the 'l' could be a '1'"],
  "unverified": "Phone read as 07700 900456, not confirmed. Job title not printed on the card.",
  "sector": "",
  "location": "",
  "fit": "",
  "notes": ""
}
```

`sector`, `location`, `fit` and `notes` are filled in after research, not from the card.

`uncertain` is the working list you ask the user about. `unverified` is the version that goes into the record and stays there, in its own column where the destination has one and in the notes where it does not. Write it as sentences a person will understand in six months, not as a debug dump. Everything the research could not confirm belongs in it too, not just the reading: a size claimed on the company's own site, an email inferred from a pattern, an identity matched on an address rather than a name.

A record with an empty `unverified` field is a claim that every value in it was confirmed against a source. Only leave it empty when that is true.

## Confidence

Three states, and they behave differently:

| State | Meaning | What happens to it |
|---|---|---|
| Read | Clearly legible | Goes in the record |
| Uncertain | Legible but ambiguous, for example `rn` against `m`, `1` against `l`, `0` against `O` | Goes in `uncertain`, and gets asked about in the report. Write the field only once confirmed |
| Absent | Not on the card | Stays blank. Never derived from the company's email pattern without saying so |

An email inferred from a pattern, for example `firstname.lastname@` because another address on the card follows that shape, is a hypothesis and must be labelled as one in the notes. It never goes in the email field as though it were printed on the card.

## The traps

**Two sides.** Most cards carry the name and title on one side, and the address, the QR code or a second language on the other. If only one side was photographed, say so and ask for the other. Do not assume the back is blank.

**Bilingual cards.** Welsh, Irish, Gaelic and other bilingual cards repeat the same job title in two languages. That is one title, not two. Record the English form unless the user works in the other language, and note that the card is bilingual, since it tells you something about the business.

**QR codes.** Read the code if it is legible in the photo, since it usually holds a vCard or a personal LinkedIn URL that is not printed anywhere else. If it is too small or blurred, ask for a closer photo rather than skipping it.

**Generic versus personal email.** `info@`, `sales@`, `hello@` and `enquiries@` are inboxes, not people. Record them, and flag in the report that there is no direct address for this person yet. Finding the direct one is a research job, not a reading job.

**Phone numbers go in exactly as printed.** Do not reformat, do not strip spaces or brackets, do not add or remove a country code, and do not infer a country from the format. If the card says `+44 7700 900123`, that is what goes in the record. If it says `07700 900123`, that goes in instead. Someone dialling it later needs what was on the card, not your tidied version of it.

Keep separate numbers in separate fields when the card labels them, because which one you use decides how the follow-up happens, and a card carrying only one mobile is usually an owner. When the card does not label them, record them in the order printed and say so rather than guessing which is which.

**Company name versus trading name.** The card shows the trading name, the filings show the registered name, and they are often different. Record what the card says in `company`, and let the Companies House lookup supply the registered entity. The registered name goes in the notes, never silently replacing what was printed.

**Titles that hide the decision maker.** Director, Managing Director, Founder, Owner and Partner mean one person can say yes. Manager, Coordinator, Executive and Lead usually mean they cannot. This changes the next action, so it belongs in the report.

**Multiple people, one card.** Some small businesses print two names. That is two records, sharing a company.

**A card that is not a business card.** Conference badges, compliment slips, a name written on a beer mat. All fine to process, but say what you were working from, because the confidence is different.

## Batches

For a pile of cards from one event:

1. Read every image first, and build the full list before researching anything.
2. Ask the open questions once, in a single message covering the whole batch, not card by card.
3. Deduplicate within the batch as well as against the CRM. Two people from the same company at the same event is one company relationship and two contacts.
4. Research in parallel batches, then write once with `--multi`.
