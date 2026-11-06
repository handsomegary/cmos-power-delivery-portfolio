; Load in the Virtuoso CIW and call portfolioAuditSchematic with local OA names.
procedure(portfolioAuditSchematic(libraryName cellName)
  let((view instance terminal netName)
    view=dbOpenCellViewByType(libraryName cellName "schematic" "schematic" "r")
    unless(view error("Cannot open %s/%s/schematic for reading.\n" libraryName cellName))
    foreach(instance view~>instances
      printf("INSTANCE %s %s/%s\n" instance~>name instance~>libName instance~>cellName)
      foreach(terminal instance~>instTerms
        netName=if(terminal~>net then terminal~>net~>name else "<unconnected>")
        printf("  %s -> %s\n" terminal~>name netName)
      )
    )
    dbClose(view)
    t
  )
)
