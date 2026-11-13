// F-72: record the text of every values-file key the /results/ cards read (lib/card-keys.lock.json), after the cards have
// been reread against it. The build names any key whose text has changed since; tests/f72.test.mjs fails until this is run.
import { writeFileSync } from 'node:fs';
import { cardHashes, cardKeyChanges, CARD_LOCK } from '../lib/results-atc.mjs';

const changed = cardKeyChanges();
for (const c of changed) console.log(`${c.id} ${c.key} (${c.was}): ${c.text}`);
writeFileSync(CARD_LOCK, JSON.stringify(cardHashes(), null, 2) + '\n');
console.log(`${CARD_LOCK}: ${changed.length} key(s) updated`);
