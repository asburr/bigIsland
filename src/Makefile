
OBJ=../obj
PCK=$(OBJ)/bigIsland

all: $(OBJ) $(PCK)/MultiWordSearch.class $(OBJ)/bigIsland/MultiRegexSearch.class $(OBJ)/bigIsland/MultiRegexExclusiveSearch.class

clean:
	rm $(PCK)/*.class


$(PCK):
	mkdir -p $(PCK)

$(PCK)/%.class: %.java
	javac -d $(OBJ) $<
