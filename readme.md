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
You need to put your telegram bot token and walkr auth_token in `config.py`.
You can obtain walkr token with Fiddler or Charles (MITM between your phone and game servers).

To start local bot use
```
pipenv run python bot.py
```

##Bridge relations
I use `graphviz` to making graph so you need to have it in your system.
You can install it on macos:
```
brew install  graphviz
```


run jupyter notebook with bridge relations:
```
pipenv run jupyter notebook mostik.ipynb
```