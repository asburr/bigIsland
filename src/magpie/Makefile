
OBJ=../../obj
PCK=$(OBJ)/magpie

all: $(OBJ) $(PCK) $(PCK)/MultiWordSearch.class $(PCK)/MultiRegexExclusiveSearch.class

clean:
	rm $(PCK)/*.class


$(PCK):
	mkdir -p $(PCK)

$(OBJ):
	mkdir -p $(OBJ)

$(PCK)/%.class: %.java
	javac -d $(PCK) $<
