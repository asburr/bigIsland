
OBJ=../../obj
## java creates package directory, see package rule in java files.
PCK=$(OBJ)/magpie

all: $(OBJ) $(PCK)/MultiWordSearch.class $(PCK)/MultiRegexExclusiveSearch.class $(PCK)/ServerFuture.class $(PCK)/Client.class $(PCK)/Server.class $(PCK)/Cli.class $(PCK)/Cfi.class

clean:
	rm -f $(PCK)/*.class

$(OBJ):
	mkdir -p $(OBJ)

$(PCK)/%.class: %.java
	javac -d $(OBJ) -cp $(OBJ) $<
