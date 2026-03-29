%%%%%%%% PSEUDO-INDENT FUNCTIONS START %%%%%%%%
% Source: https://wiki.lilypond.community/wiki/Indenting_individual_systems

pseudoIndents =
#(define-music-function (name-tweaks left-indent right-indent)
   ((markup-list? '()) number? number?)

   (define (warn-stretched p1 p2)
     (ly:input-warning
      (*location*)
      (G_
       " \\pseudoIndents ~s ~s is stretching staff; expect distorted layout")
      p1 p2))

   (let*
       ((narrowing (+ left-indent right-indent))
        (set-staffsymbol!
         (lambda (staffsymbol-grob)
           (let*
               ((left-bound (ly:spanner-bound staffsymbol-grob LEFT))
                (left-moment (ly:grob-property left-bound 'when))
                (capo? (moment<=? left-moment ZERO-MOMENT))
                (layout (ly:grob-layout staffsymbol-grob))
                (lw (ly:output-def-lookup layout 'line-width))
                (indent (ly:output-def-lookup
                         layout
                         (if capo? 'indent 'short-indent)))
                (old-stil (ly:staff-symbol::print staffsymbol-grob))
                (staffsymbol-x-ext (ly:stencil-extent old-stil X))
                (ss-t (ly:staff-symbol-line-thickness
                       staffsymbol-grob))
                (pristine? (<= 0 (car staffsymbol-x-ext) ss-t))
                (leftmost-x (+ indent (if pristine? 0 narrowing)))
                (narrowing_ (if pristine? narrowing 0))
                (old-width (+ (interval-length staffsymbol-x-ext)
                              ss-t))
                (new-width (- old-width narrowing_))
                (new-rightmost-x (+ leftmost-x new-width))
                (junk (ly:grob-set-property! staffsymbol-grob
                                             'width new-rightmost-x))
                (in-situ-stil (ly:staff-symbol::print
                               staffsymbol-grob))
                (new-stil (ly:stencil-translate-axis in-situ-stil
                                                     narrowing_
                                                     X))
                (new-x-ext (ly:stencil-extent new-stil X)))
             (ly:grob-set-property! staffsymbol-grob 'stencil
                                    new-stil)
             (ly:grob-set-property! staffsymbol-grob 'X-extent
                                    new-x-ext))))

        (set-X-offset!
         (lambda (margin-grob)
           (let* ((old (ly:grob-property-data margin-grob 'X-offset))
                  (new (lambda (grob)
                         (+ (if (procedure? old) (old grob) old)
                            narrowing))))
             (ly:grob-set-property! margin-grob 'X-offset new))))

        (tweak-text!
         (lambda (i-name-grob mkup)
           (when (and (markup? mkup)
                      (not (string=? (markup->string mkup) "*")))
             (ly:grob-set-property! i-name-grob 'long-text mkup)
             (ly:grob-set-property! i-name-grob 'text mkup))))

        (install-narrowing
         (lambda (leftedge-grob)
           (let*
               ((sys (ly:grob-system leftedge-grob))
                (all-grobs (ly:grob-array->list
                            (ly:grob-object sys 'all-elements)))
                (grobs-named
                 (lambda (name)
                   (filter (lambda (x)
                             (eq? name (grob::name x))) all-grobs)))
                (first-leftedge-grob (list-ref
                                      (grobs-named 'LeftEdge) 0))
                (relsys-x-of (lambda (g)
                               (ly:grob-relative-coordinate g sys X)))
                (leftedge-x (relsys-x-of first-leftedge-grob))
                (leftedged? (lambda (g)
                              (= (relsys-x-of g) leftedge-x)))
                (leftedged-ss (filter leftedged?
                                      (grobs-named 'StaffSymbol))))
             (when (eq? leftedge-grob first-leftedge-grob)
               (for-each set-staffsymbol! leftedged-ss)
               (for-each set-X-offset! (grobs-named 'SystemStartBar))
               (for-each set-X-offset! (grobs-named 'InstrumentName))
               (for-each tweak-text! (grobs-named 'InstrumentName)
                         name-tweaks))))))

     (when (negative? narrowing)
       (warn-stretched left-indent right-indent))
     #{
       \break
       \once \override Score.LeftEdge.X-extent =
         #(cons narrowing narrowing)
       \once \override Score.LeftEdge.after-line-breaking =
         #install-narrowing
       \overrideProperty Score.NonMusicalPaperColumn
                         .line-break-system-details
                         .X-offset #(- right-indent)
       \once \override Score.BarNumber.horizon-padding =
         #(max 1 (- 1 narrowing))
     #}))

pseudoIndent =
#(define-music-function (name-tweaks left-indent)
   ((markup-list? '()) number?)
   #{
     \pseudoIndents $name-tweaks $left-indent 0
   #})
%%%%%%%% PSEUDO-INDENT FUNCTIONS END %%%%%%%%
