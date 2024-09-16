# Minesweeper

The classic minesweeper game, built to test domonic and fast-api

##### setup

```
	python3 -m venv venv
	. venv/bin/activate
	python -m pip install -r requirements.txt
```

##### running

```
    python minesweeper.py
```

## about

- Decisions on users success are made on the server side aysnc.

- Threads are used to speed-up checking the tiles.

- If you make HUGE grid. Increase recursion limit at the top of the file. i.e

```
    print(sys.getrecursionlimit())
    sys.setrecursionlimit(5000)
```

<img src="https://github.com/byteface/minesweeper/blob/master/images/screenshot.png" width="100%" height="auto" />
