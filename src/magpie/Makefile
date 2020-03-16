
OBJ=../../obj
## java creates package directory, see package rule in java files.
PCK=$(OBJ)/magpie

all: $(OBJ) $(PCK)/MultiWordSearch.class $(PCK)/MultiRegexExclusiveSearch.class $(PCK)/Client.class $(PCK)/Server.class

clean:
	rm $(PCK)/*.class

$(OBJ):
	mkdir -p $(OBJ)

$(PCK)/%.class: %.java
	javac -d $(OBJ) -cp $(OBJ) $<
