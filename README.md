# community_got_class

Guessing game - which of these are real classes offered at my local community college?

Portland Community College is great. Several family members have taken classes there, which means we get the class catalog sent to us, and boy do some of these look fun! So, I turned a few of our choice picks into a game, with AI-generated fake classes sprinkled in to turn it into a fake-or-not style game in the long tradition that began (for me) with the classic 'Big Data or Pokemon?' quiz back in the day.

The app is made with FastHTML, with tailwind UI prototyped with claude and converted using [this tool](https://h2f.answer.ai/). It's deployed on [Railway](https://railway.com/). Guesses (tied to session ID) are stored in an sqlite DB so that you can see stats on how many people guess right for the different pairings. 

Let me know if you have any questions,

Have fun :)

References:

PCC spring community class list: https://www.pcc.edu/community/wp-content/uploads/sites/202/2019/11/SP25_PCC_CED_021425.pdf
FastHTML: https://docs.fastht.ml/
