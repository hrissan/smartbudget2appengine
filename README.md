## what's this

This was a server-side of Smart Budget 2 app running on Google App Engine.

Reason for using Google, not iCloud was simple - Smart Budget implemented cloud sync in 2009, there were no Apple cloud at that time.

Later first iCloud versions were very buggy so Smart Budget was reluctant to switch, and also there were plans (never materialized) to release Web and
Android versions.

So here it is. Smart Budget 2 used point to point encryption, so Smart Budget 2 developers could never decrypt user data in the cloud.

Later this decision foiled a deal to sell Smart Budget 2 to certain western organization for big $$$.

As soon as they learned they could not spy on users, they lost interest completely.

## how it works

### DB name

When DB is created, a long random database name string is generated. To access DB you need this string, you cannot guess it (it is sufficiently long), and there is no user-facing API to iterate.

So to download someone's DB, first you need to know this string, which is either transferred between devices automatically via iCloud sync, so any DB you add on your iPhone magically appears on your iPad and other devices.

Or you can explicitly share DB from app by pressing button and sending e-mail with special link, containin DB name and encryption key (encryption is discussed later in this document).

### DB organization and sync

Each DB is organized as a changelog, so you start from empty DB, then add a change to it, which could be adding account, adding deleting or modifying expense, etc.

Every change has an incrementing ID, starting from 1 then 2 then 3, etc. Server acts as an arbiter, deciding on order of changes.

Each device has a fully synced prefix of changes from server, for example [1, 2, 3] and then when you edit something, it adds changes to the suffix.

Let's say device A added changes A1 and A2, so changes in local DB on device A are [1, 2, 3] [A1, A2]. 

Simultneously other device B could have added changes B1 and B2, so changes in local DB on device B are [1, 2, 3] [B1, B2].

Now, some device will sync to server first, let's say it is A, it sends offset 3 and its changes [A1, A2], and server adds them to server storage, resulting in list [1, 2, 3, A1, A2], now A1 and A2 got permanent IDs 4 and 5, and we we will refer to them as 4 and 5, so in server DB list looks like [1, 2, 3, 4, 5], device A gets suffix of this list starting from offset 3 as a response to sync RPC call, and this is new local DB on device A.

Now when device B sends it's own changes [B1, B2] together with starting offset 3, server instead replies with existing changes [4, 5], and device B first adds new changes [4, 5] to its DB, then rebases (applies after), its own changes [B1, B2], so list on device B temporarily looks like [1, 2, 3, 4, 5] [B1, B2].

But during rebase, conflicts can occur, for example, 4 could be deleting account, and B1 is renaming that same account.

Smart Budget 2 uses automatic conflict resolution, for each possible conflict, there is decision selected, which loses least amount of information. In the example above (deleteing then renaming account) account will be restored then renamed (no information is ever deleted in this design, because list of changes never changes after sync, so everything you did exists forever, including state of account at the point of deletion, so everything can be restored). Rarely
change can be NOP after rebase (changing account to the same name, for example), in which case change is simply dropped from the local changes list during rebase as an optimization.

Returning to our sync, after B gets new list from server and successfully rebases it's local list of changes, it syncs again, sending new offset 5 and its
changes [B1, B2] and now server successfully adds changes to the server DB, assigning ids 6 and 7 to them, so new server list is [1, 2, 3, 4, 5, 6, 7].

Then server sends push notification to A, so A will sync again, sending its offset 5 and no changes, and will get [6, 7] and add them to local DB.

This process advances either server or local list of changes after every sync, so progress is made every iteration, and all devices will quickly get
the same list of changes, resulting in the same data displayed to the user.

## Details on local storage

Each devices stores list of changes in SQLite database together with result of playing back those changes (state). 

So there could be million expenses on account and it could be renamed several times through history, but most recent account name, balance, and list of expenses to display is stored separately in the same SQLite database, so app will start and show information immediately, without iterating through all changes. There were actual user databases with million+ changes and still after initial sync, Smart Budget app will start immediately.

List of changes is simple, and format of each change itself is also simple, because this format must be parsed and replayed by all future version of Smart Budget.

On the other hand format of storing state information can be changed and was changed several times during app lifetime. When app starts after update, it will notice state format version (also stored in the same DB) is old. App will then clear state and replay all changes from the start, which can take substantial time, but after this is done, app will start immediately again. If app is closed during such replay, only little progress will be lost, because after replaying
sertain amount of changes, app will save SQLite database state to disk.

## DB encryption and authentication

When DB is first generated, not only random DB name, but also random symmetric encryption key is generated.

Every change will be encrypted on device A before sending to server, so from the server point of view, every change is completely opaque byte string,
which can be synched, but cannot be looked into. Device B must have the same encryption key to be able to decrypt change and show it to the user.

Exactly as DB name, encryption key is automatically transferred between user's devices vie iCloud, or can be sent via e-mail when user presser "Share DB" button. 

App tries decrypting changes before integrating into local DB, so will not integrate changes sent by attacker who does not know encryption key, if that attacker somehow gets control of Smart Budget server.

Smart Budget app does not send and server does not store any tracking information (IP addresses, any information about user device,
any information about user, no e-mail address, nothing). 

Smart Budget app sends and server stores payment receipts from App Store, so if database is added on device
with full version of Smart Budget, transaction limit is removed. But those payment receipts are correctly
encrypted by Apple and are themselves random strings which cannot be tied to user.

## exchange rates

Those are downloaded first by server side into server DB, then downloaded with separate RPC call by apps.
This is done to limit amount of API calls to exchange rate providers.

API keys are replaced in code with `censored` string, so if you want to deploy, get and insert your own API keys.

## Great Wall proxy

Google App engine often had bad or no connectivity from China, so simple proxy was deployed in Hong Kong and Singapore, sending
data between Smart Budget app and server.

## App Removal

All app data in the cloud was wiped by Google in 2025 together with my account for payment with foreign bank card,
stating sanctions violation.
