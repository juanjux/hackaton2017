- Inhabilitate all the preprocessor macros that are not branching ones, renaming
  #whatever to _#_whatever. Leave only the #ifdef

Por cada #ifdef SYMBOL, ejecutar `gcc -E -DSYMBOL` y `gcc -E -USYMBOL`
