Unicorn Rental Return Queue Processor.
======

## What does this code do?
I read about this really cool service called SQS - It a completely managed queue service by AWS and it scales almost instantly based on your requirements. Since our Raspberry Pi burned out this week, which I warned Kyle about like a million times, I think I am going to try and use this in our new modern Rental Return processor.

I already changed the rental return policy from the customer website side, so all returns are now being placed as messages in the SQS queue. That's so much easier, and I bought myself a little more time because those messages will stay there for a while until I get this code going.

This code pretty much just takes messages from SQS, processes the rental duration and then relays that to my SpaceInvaders backend for storage. There really isn't that much work to make it happen. That being said my code is _super buggy_ right now, so I should probably think about hardening this code at some point.
