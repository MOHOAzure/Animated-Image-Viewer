# Run
```sh
pipenv run python main.py
```

# Dev
```sh
get-command python | format-list # check python on windows

pipenv shell

pipenv install
```

# Make exe
```sh
pyinstaller --onefile --windowed --add-data "version.txt;." ./main.py
```