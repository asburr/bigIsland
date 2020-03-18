
OBJ=../../obj
PCK=$(OBJ)/hallelulajah

all: $(OBJ) $(PCK) $(PCK)/Hallelulajah.class

clean:
	rm -f $(PCK)/*.class


$(PCK):
	mkdir -p $(PCK)

$(OBJ):
	mkdir -p $(OBJ)

$(PCK)/%.class: %.java
	javac -d $(OBJ) -classpath $(OBJ) $<
