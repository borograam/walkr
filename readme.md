before install ensure you have `pipenv`
You can install it on macos:
```
brew install pipenv
```

install:
```
git clone git@github.com:borograam/walkr.git && cd walkr
pipenv install
```

##Telegram Bot
You need to put your telegram bot token in `config.py`.

Before start the bot you need to init sqlite3 database and add at least one walkr token in db.
You can obtain walkr token with Fiddler or Charles (MITM between your phone and game servers).

```shell
cd bot
pipenv run python cli.py --db_create_tables
pipenv run python cli.py --token spacewalk:...
```

To start local bot use
```shell
cd bot
pipenv run python bot.py
```

##Bridge relations
I use `graphviz` to making graph so you need to have it in your system.
You can install it on macos:
```shell
brew install graphviz
```


run jupyter notebook with bridge relations:
```shell
pipenv run jupyter notebook mostik.ipynb
```